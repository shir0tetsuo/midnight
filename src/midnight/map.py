from .storage import Store
from .version import __version__
from .maps import maps_directory
from .signature import MachineSignature
import os
#from 
from typing import Literal, Optional
import numpy as np
from datetime import datetime, timezone



class BuiltMap(Store):

    # NOTE : Warps will be defined by the tile type.

    class BadHeaderError(Exception):
        '''
        Indicates something went wrong when parsing the header or magic header data.
        '''
        def __init__(self, *message):
            super().__init__(*message)

    HEADER_SIZE = 128
    '''The size of the file header in bytes before the magic header.'''

    class FHeaderSchema:
        '''Holds slices and number of floats for the magic header.'''
        M_SIG = slice(0,8)
        '''Machine Signature'''
        TIMESTAMP = slice(8,10)
        MAP_SIZE = slice(10,12)

        _FLOATS = 12
        _F_SIZE = _FLOATS*np.dtype('<f4').itemsize  # bytes
    
    store_type  = '32-bit'

    @staticmethod
    def split_float64(x):
        hi = np.dtype('<f4').type(x)
        lo = np.dtype('<f4').type(x - np.float64(hi))
        return hi, lo

    @staticmethod
    def combine_float32_or_f4(hi, lo):
        return np.float64(hi) + np.float64(lo)

    @staticmethod
    def split_timestamp(ts):
        sec = np.dtype('<f4').type(int(ts))
        frac = np.dtype('<f4').type(ts - int(ts))
        return sec, frac

    def __init__(
            self, 
            identifier:str,
            MapType: Literal['local', 'built-in', 'dungeon'] = 'built-in',
            NewMapSize: tuple[int, int] = (128, 128)
        ):
        super().__init__(identifier=identifier, suffix='.map.bin')

        # If built-in use the maps directory
        if MapType == 'built-in':
            self.basepath = maps_directory()
            self.path = self.basepath / f'{identifier}{self.suffix}'

        self.identifier = identifier
        if (len(self.identifier)>32):
            raise ValueError('The identifier should not be over 32 characters.')

        self.created = None  # Timestamp of created for file (original)

        # New Map Coordinates (applies to new maps only)
        self.NewMap_y, self.NewMap_x = NewMapSize
        self.NewMap_y_f32 = np.dtype('<f4').type(self.NewMap_y)
        self.NewMap_x_f32 = np.dtype('<f4').type(self.NewMap_x)

        self.MapType = MapType
        self.MagicHeader: Optional[np.memmap] = None
        self.data = self._open_memmap()

        pass

    @property
    def header(self):
        h = (
            b"MID.NIGHTMOONBEAM_" 
            + __version__.encode("utf-8") 
            + b'_'
            + self.store_type.encode("utf-8")
            + b'_'
            + self.MapType.encode("utf-8")
            + b'_'
            + self.identifier.encode('utf-8')
            + b'_.map.bin'
        )
        return h.ljust(self.HEADER_SIZE, b"\x00")
    
    
    def _open_memmap(self):
        with self.lock:

            # --- FILE CREATION ---
            if not self.exists:
                with open(self.path, "wb") as f:
                    f.write(self.header)
                    f.truncate(self.HEADER_SIZE + BuiltMap.FHeaderSchema._F_SIZE)
        
                magic_header = np.memmap(
                    self.path,
                    dtype=np.dtype('<f4'),
                    mode="r+",
                    offset=self.HEADER_SIZE,
                    shape=(BuiltMap.FHeaderSchema._FLOATS,)
                )
                MAP_SIZE=magic_header[BuiltMap.FHeaderSchema.MAP_SIZE]
                MAP_SIZE[0] = self.NewMap_y_f32
                MAP_SIZE[1] = self.NewMap_x_f32

                sec, frac = BuiltMap.split_timestamp(datetime.now(timezone.utc).timestamp())
                magic_header[BuiltMap.FHeaderSchema.TIMESTAMP] = (sec, frac)

                magic_header[BuiltMap.FHeaderSchema.M_SIG] = MachineSignature.Fingerprint()

                magic_header.flush()

                expected_size = int(MAP_SIZE[0]) * int(MAP_SIZE[1])
                expected_size_bytes = (
                    expected_size * np.dtype('<f4').itemsize
                    # expected_size * np.dtype(np.float32).itemsize
                )

                # Write the expected 128*128 bytes flushed as \x00
                with open(self.path, "r+b") as f:
                    f.truncate(self.HEADER_SIZE + BuiltMap.FHeaderSchema._F_SIZE + expected_size_bytes)

            else:
                magic_header = np.memmap(
                    self.path,
                    dtype=np.dtype('<f4'),
                    mode="r+",
                    offset=self.HEADER_SIZE,
                    shape=(BuiltMap.FHeaderSchema._FLOATS,)
                )

            # Return the magic header
            self.MagicHeader = magic_header

            # Validation
            with open(self.path, "rb") as f:
                header = f.read(self.HEADER_SIZE)

            decoded = header.decode("utf-8", errors="replace").rstrip("\x00")

            # Fast prefix check (cheap reject)
            if not header.startswith(b"MID.NIGHTMOONBEAM_"):
                raise BuiltMap.BadHeaderError(f"Bad header magic: {decoded}")
            
            # Obtain decoded parts from the header
            parts = decoded.split("_")

            if len(parts) < 5:
                raise BuiltMap.BadHeaderError("Corrupt header (invalid format)")
            
            # Check the header to make sure the dtype and maptype is correct
            _, _version, _dtype_tag, _map_type, _identifier = parts[:5]

            if _dtype_tag != self.store_type:
                raise BuiltMap.BadHeaderError(
                    f"Store type mismatch: Expected {self.store_type}, got {_dtype_tag}"
                )
            if _map_type != self.MapType:
                raise BuiltMap.BadHeaderError(f'Map type is {_map_type}, but instance is {self.MapType}')
            
            MAP_SIZE = magic_header[BuiltMap.FHeaderSchema.MAP_SIZE]
            
            # Get the expected and actual size of bytes and compare
            expected_size = (
                int(   np.nan_to_num(MAP_SIZE[0], nan=self.NewMap_y) ) 
                * int( np.nan_to_num(MAP_SIZE[1], nan=self.NewMap_x) )
            )
            actual_size   = self.size_bytes
            expected_file_size = (
                self.HEADER_SIZE +
                BuiltMap.FHeaderSchema._F_SIZE +
                expected_size * np.dtype('<f4').itemsize
            )
            if actual_size != expected_file_size:
                raise BuiltMap.BadHeaderError(
                    f"Invalid map file size: "
                    f"expected {expected_file_size}, got {actual_size}"
                )

            # Get the timestamp, convert to a datetime object
            # and put in self.created for ease of reference
            sec, frac = magic_header[BuiltMap.FHeaderSchema.TIMESTAMP]
            self.created = datetime.fromtimestamp(
                float(self.combine_float32_or_f4(sec, frac)),
                tz=timezone.utc
            )

            # Copy magic header machine signature to internal mangled
            self.__M_SIG = magic_header[BuiltMap.FHeaderSchema.M_SIG]
            
            # Return the data memmap
            return np.memmap(
                self.path,
                dtype=np.dtype('<f4'),
                mode="r+",
                offset=(self.HEADER_SIZE + BuiltMap.FHeaderSchema._F_SIZE),
                shape=(expected_size,)
            )
        
    @property
    def is_file_authority(self):
        if self.__M_SIG is None:
            return False
        
        M_SIG = MachineSignature.Fingerprint()
        return np.array_equal(
            np.asarray(M_SIG).view('<u4'),
            np.asarray(self.__M_SIG).view('<u4')
        )
       
    def _get_fd(self):
        return self.path.open("r+b").fileno()

    def flush(self, fsync:bool=False):
        with self.lock:
            try:
                self.data.flush()
                if fsync:
                    with open(self.path, "r+b") as f:
                        os.fsync(f.fileno())
            except Exception as e:
                raise IOError(f'Failed to flush SaveFile {self.path}: {type(e)}: {e}')

