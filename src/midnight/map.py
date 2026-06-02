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

    HEADER_SIZE = 128

    class FHeaderSchema:
        M_SIG = slice(0,8)
        TIMESTAMP = slice(8,10)
        MAP_SIZE = slice(10,12)

        DEFAULT_MAP_SIZE = np.float32(128.0) # np.dtype('<f4')(128)
        _FLOATS = 12
        _F_SIZE = _FLOATS*np.dtype('<f4').itemsize  # bytes
    
    store_type  = '32-bit'

    @staticmethod
    def split_float64(x):
        hi = np.dtype('<f4')(x)
        lo = np.dtype('<f4')(x - np.float64(hi))
        return hi, lo

    @staticmethod
    def combine_float32_or_f4(hi, lo):
        return np.float64(hi) + np.float64(lo)

    @staticmethod
    def split_timestamp(ts):
        sec = np.dtype('<f4')(int(ts))
        frac = np.dtype('<f4')(ts - int(ts))
        return sec, frac

    def __init__(
            self, 
            identifier:str,
            MapType: Literal['local', 'built-in', 'dungeon'] = 'built-in'
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

        # NOTE : Warps will be defined by the tile type.

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
                MAP_SIZE[0] = BuiltMap.FHeaderSchema.DEFAULT_MAP_SIZE
                MAP_SIZE[1] = BuiltMap.FHeaderSchema.DEFAULT_MAP_SIZE

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

            self.MagicHeader = magic_header

            # Validation
            with open(self.path, "rb") as f:
                header = f.read(self.HEADER_SIZE)

            decoded = header.decode("utf-8", errors="replace").rstrip("\x00")

            # Fast prefix check (cheap reject)
            if not header.startswith(b"MID.NIGHTMOONBEAM_"):
                raise ValueError(f"Bad header magic: {decoded}")
            
            parts = decoded.split("_")

            if len(parts) < 5:
                raise ValueError("Corrupt header (invalid format)")
            
            _, _version, _dtype_tag, _map_type, _identifier = parts[:5]

            if _dtype_tag != self.store_type:
                raise TypeError(
                    f"Store type mismatch: Expected {self.store_type}, got {_dtype_tag}"
                )
            
            MAP_SIZE = magic_header[BuiltMap.FHeaderSchema.MAP_SIZE]
            
            expected_size = int(np.nan_to_num(MAP_SIZE[0], nan=128)) * int(np.nan_to_num(MAP_SIZE[1], nan=128))

            actual_size = self.size_bytes

            expected_file_size = (
                self.HEADER_SIZE +
                BuiltMap.FHeaderSchema._F_SIZE +
                expected_size * np.dtype('<f4').itemsize
            )

            if actual_size != expected_file_size:
                raise ValueError(
                    f"Invalid map file size: "
                    f"expected {expected_file_size}, got {actual_size}"
                )

            sec, frac = magic_header[BuiltMap.FHeaderSchema.TIMESTAMP]
            self.created = datetime.fromtimestamp(
                float(self.combine_float32_or_f4(sec, frac)),
                tz=timezone.utc
            )

            self.__M_SIG = magic_header[BuiltMap.FHeaderSchema.M_SIG]
            
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
            np.asarray(M_SIG, dtype='<u4'),
            np.asarray(self.__M_SIG, dtype='<u4')
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

