from .storage import Store
from .version import __version__
from .maps import maps_directory
import os
#from 
from typing import Literal
import numpy as np


class BuiltMap(Store):

    HEADER_SIZE = 128
    store_type  = '32-bit'

    @staticmethod
    def split_float64(x):
        hi = np.float32(x)
        lo = np.float32(x - np.float64(hi))
        return hi, lo

    @staticmethod
    def combine_float32(hi, lo):
        return np.float64(hi) + np.float64(lo)

    @staticmethod
    def split_timestamp(ts):
        sec = np.float32(int(ts))
        frac = np.float32(ts - int(ts))
        return sec, frac

    def __init__(
            self, 
            identifier:str,
            MapType: Literal['local', 'built-in', 'dungeon'] = 'built-in'
        ):
        super().__init__(identifier=identifier, suffix='.map.bin')

        # If built-in use the maps directory
        if MapType == 'built-in':
            self.basepath = maps_directory
            self.path = self.basepath / f'{identifier}{self.suffix}'

        self.identifier = identifier
        if (len(self.identifier)>32):
            raise ValueError('The identifier should not be over 32 characters.')

        # NOTE : Casting is going to be different here,
        #        We'll use a SECOND HEADER to retrieve how
        #        big the file should be.

        self.MapType = MapType

        self.offset = [
            # basic file information offset
            BuiltMap.HEADER_SIZE #// np.dtype(np.float32).itemsize
        ]

        # TODO : Schema for the second header
        # - timestamp
        # - map size
        # - warps (16 available) if not 0
        # 🤔

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
    


    def _get_fd(self):
        return self.path.open("r+b").fileno()

    # def flush(self, fsync:bool=False):
    #     with self.lock:
    #         try:
    #             self.data.flush()
    #             if fsync:
    #                 with open(self.path, "r+b") as f:
    #                     os.fsync(f.fileno())
    #         except Exception as e:
    #             raise IOError(f'Failed to flush SaveFile {self.path}: {type(e)}: {e}')

