from .storage import Store
from .version import __version__
from .maps import maps_directory
from .signature import MachineSignature
import os
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

        # We store the magic header as 12 uint32 slots (48 bytes):
        # - 0..7 : machine signature (8 x uint32)
        # - 8..9 : timestamp bits as float32 bit-patterns (2 x uint32)
        # - 10..11: map size (y,x) as uint32
        _SLOTS = 12
        _F_SIZE = _SLOTS * np.dtype('<u4').itemsize  # bytes
    
    store_type  = '32-bit'

    @staticmethod
    def split_float64(x):
        hi = np.float32(x).astype('<f4')
        lo = np.float32(x - np.float64(hi)).astype('<f4')
        return hi, lo

    @staticmethod
    def combine_float32_or_f4(hi, lo):
        return np.float64(hi) + np.float64(lo)

    @staticmethod
    def split_timestamp(ts):
        sec = np.float32(int(ts)).astype('<f4')
        frac = np.float32(ts - int(ts)).astype('<f4')
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
        # store integer sizes as uint32 for the header
        self.NewMap_y_u32 = np.uint32(self.NewMap_y)
        self.NewMap_x_u32 = np.uint32(self.NewMap_x)

        self.MapType = MapType
        self.MagicHeader: Optional[np.memmap] = None
        self.data = self._open_memmap()

        pass

    @property
    def header(self):
        # Use ASCII Unit Separator (0x1F) as a delimiter which
        # we will disallow in identifiers.
        delim = b'\x1f'
        h = (
            b"MID.NIGHTMOONBEAM" + delim
            + __version__.encode("utf-8")
            + delim
            + self.store_type.encode("utf-8")
            + delim
            + self.MapType.encode("utf-8")
            + delim
            + self.identifier.encode('utf-8')
            + delim
            + b'map.bin'
        )
        return h.ljust(self.HEADER_SIZE, b"\x00")
    
    
    def _open_memmap(self):
        with self.lock:

            # --- FILE CREATION ---
            # We'll compute the final required file size and create it
            # fully before opening memmaps. This avoids truncating an
            # active memmap which can be fragile on some OSes.
            data_dtype = np.dtype('<u2')  # main map data: uint16 little-endian
            header_dtype = np.dtype('<u4')

            expected_size = int(self.NewMap_y) * int(self.NewMap_x)
            expected_size_bytes = expected_size * data_dtype.itemsize
            total_size = self.HEADER_SIZE + BuiltMap.FHeaderSchema._F_SIZE + expected_size_bytes

            if not self.exists:
                # validate identifier won't contain delim and header fits
                delim_char = '\x1f'
                if delim_char in self.identifier:
                    raise ValueError('Identifier may not contain the unit-separator character')

                header_bytes = self.header
                if len(header_bytes) > self.HEADER_SIZE:
                    raise BuiltMap.BadHeaderError('Encoded header too large for HEADER_SIZE')

                # create the full file size first
                with open(self.path, 'wb') as f:
                    f.write(header_bytes)
                    f.truncate(total_size)

                # open magic header as uint32 slots
                magic_header = np.memmap(
                    self.path,
                    dtype=header_dtype,
                    mode='r+',
                    offset=self.HEADER_SIZE,
                    shape=(BuiltMap.FHeaderSchema._SLOTS,)
                )

                # MAP_SIZE (store as uint32)
                magic_header[BuiltMap.FHeaderSchema.MAP_SIZE][0] = np.uint32(self.NewMap_y)
                magic_header[BuiltMap.FHeaderSchema.MAP_SIZE][1] = np.uint32(self.NewMap_x)

                # Timestamp: store float32 bit patterns into uint32 slots
                ts = datetime.now(timezone.utc).timestamp()
                sec = np.float32(int(ts)).astype('<f4')
                frac = np.float32(ts - int(ts)).astype('<f4')
                sec_bits = np.array([sec], dtype='<f4').view('<u4')[0]
                frac_bits = np.array([frac], dtype='<f4').view('<u4')[0]
                magic_header[BuiltMap.FHeaderSchema.TIMESTAMP][0] = np.uint32(sec_bits)
                magic_header[BuiltMap.FHeaderSchema.TIMESTAMP][1] = np.uint32(frac_bits)

                # Machine signature (uint32 array)
                magic_header[BuiltMap.FHeaderSchema.M_SIG] = MachineSignature.Fingerprint()

                # flush the small header
                magic_header.flush()

            else:
                magic_header = np.memmap(
                    self.path,
                    dtype=np.dtype('<u4'),
                    mode='r+',
                    offset=self.HEADER_SIZE,
                    shape=(BuiltMap.FHeaderSchema._SLOTS,)
                )

            # Return the magic header
            self.MagicHeader = magic_header

            # Validation
            with open(self.path, "rb") as f:
                header = f.read(self.HEADER_SIZE)

            decoded = header.decode("utf-8", errors="replace").rstrip("\x00")

            # Fast prefix check (cheap reject)
            delim = '\x1f'
            if not header.startswith(b"MID.NIGHTMOONBEAM" + delim.encode()):
                raise BuiltMap.BadHeaderError(f"Bad header magic: {decoded}")

            # Obtain decoded parts from the header
            parts = decoded.split(delim)

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
            # Map sizes are stored as uint32
            expected_size = int(MAP_SIZE[0]) * int(MAP_SIZE[1])
            actual_size   = self.size_bytes
            expected_file_size = (
                self.HEADER_SIZE +
                BuiltMap.FHeaderSchema._F_SIZE +
                expected_size * np.dtype('<u2').itemsize
            )
            if actual_size != expected_file_size:
                raise BuiltMap.BadHeaderError(
                    f"Invalid map file size: "
                    f"expected {expected_file_size}, got {actual_size}"
                )

            # Get the timestamp, convert to a datetime object
            # and put in self.created for ease of reference
            # Timestamp bits are stored as uint32 containing float32 bit patterns
            sec_bits, frac_bits = magic_header[BuiltMap.FHeaderSchema.TIMESTAMP]
            sec_f = np.array([sec_bits], dtype='<u4').view('<f4')[0]
            frac_f = np.array([frac_bits], dtype='<u4').view('<f4')[0]
            self.created = datetime.fromtimestamp(float(self.combine_float32_or_f4(sec_f, frac_f)), tz=timezone.utc)

            # Copy machine signature (uint32s)
            self.__M_SIG = magic_header[BuiltMap.FHeaderSchema.M_SIG].copy()

            # Return the data memmap as uint16 array (little-endian)
            return np.memmap(
                self.path,
                dtype=data_dtype,
                mode='r+',
                offset=(self.HEADER_SIZE + BuiltMap.FHeaderSchema._F_SIZE),
                shape=(expected_size,)
            )
        
    @property
    def is_file_authority(self):
        if self.__M_SIG is None:
            return False
        
        M_SIG = MachineSignature.Fingerprint()
        # Both are uint32 arrays; compare directly
        return np.array_equal(np.asarray(M_SIG, dtype='<u4'), np.asarray(self.__M_SIG, dtype='<u4'))
       
    def _get_fd(self):
        return self.path.open("r+b").fileno()

    def flush(self, fsync:bool=False):
        with self.lock:
            try:
                # flush magic header (small) and main data
                if self.MagicHeader is not None:
                    try:
                        self.MagicHeader.flush()
                    except Exception:
                        pass
                self.data.flush()
                if fsync:
                    with open(self.path, "r+b") as f:
                        os.fsync(f.fileno())
            except Exception as e:
                raise IOError(f'Failed to flush SaveFile {self.path}: {type(e)}: {e}')

