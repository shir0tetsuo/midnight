import numpy as np
from pathlib import Path
import os
import threading
import platform
from typing import Union

class BinStore:
    '''Store numpy arrays of numpy floats into binary files.'''

    _system = {}

    def __init__(
            self, 
            identifier:str,
            dtype: Union[       # max_n
                np.uint8,       # 0 to 255 (8-bit), 1 byte per value
                np.int8,        # -128 to 127 (8-bit), 1 byte per value
                np.uint16,      # 0 to 65535 (16-bit), 2 bytes per value
                np.uint32,      # 0 to 4,294,967,295 (32-bit), 4 bytes per value
                np.float16,     # 65504.0 (16-bit)
                np.float32,     # 3.4e38 (32-bit)
                np.float64,     # 1.8e308 (64-bit)
                np.longdouble   # 1.2e4932 (platform-dependent)
            ] = np.float32,
            size: int = 512  # Maximum size of chunks to read
        ):

        self.lock = threading.RLock()

        # Get system, path
        self._system.setdefault('system', platform.system())
        self.basepath = self.get_basepath()
        self.path:Path = self.basepath / identifier + '.bin'

        # Maximum float store size
        self.dtype = dtype
        self.size = size

        self.data = None

    @property
    def system(self):
        return self._system.get('system', 'Unknown')
    
    @property
    def exists(self):
        return self.path.exists()

    def get_basepath(self):
        '''Get the base path, also create the directory.'''
        system = self.system
        app_name = 'shir0tetsuo_midnight'
        if system == 'Windows':
            base = Path(os.getenv("APPDATA", Path.home()))
            path = base / app_name
        elif system == "Darwin":
            path = Path.home() / "Library" / "Application Support" / app_name
        else:
            xdg = os.getenv("XDG_DATA_HOME", Path.home() / ".local" / "share")
            path = Path(xdg) / app_name
        
        try:
            with self.lock:
                path.mkdir(parents=True, exist_ok=True)
        except Exception:
            raise

        return path
    
    def formatted(self, l:list[int|float]) -> np.ndarray:
        return np.asarray(l, dtype=self.dtype)
    
    @classmethod
    def chunked(cls, identifiers: list[str]):
        '''Generator yielding (identifier, loaded_data) for each identifier'''
        # eg. data = {i: next_float32 for i, next_float32 in BinStore.chunked(['health', 'points'])}
        # or  data_list = list(BinStore.chunked(['health', 'points']))  # (tuples)
        for identifier in identifiers:
            store = cls(identifier)
            yield identifier, store.loaded
    
    def empty_array(self):
        return np.zeros(self.size, dtype=self.dtype)
    
    def values_until_zero(self):
        '''Generator yielding values from loaded data until first zero'''
        for value in self.loaded:
            if int(value) == 0:
                break
            yield value    
  
    @property
    def loaded(self):

        if self.data is not None:
            return self.data
        
        with self.lock:
            try:
                with open(self.path, "rb") as f:
                    loaded = np.fromfile(f, dtype=self.dtype, count=self.size)
            except FileNotFoundError:
                empty_array = self.empty_array()
                self.data = empty_array
                return self.data
            except Exception:
                raise

        self.data = loaded
        return loaded
    
    # data = np.array([1.0, 2.0, 3.0, 4.0, 5.0], dtype=np.float32)
    def write(self, arr: np.ndarray):
        arr = np.asarray(arr, dtype=self.dtype).ravel()

        if arr.size > self.size:
            raise ValueError(f"Expected {self.size} elements, got {arr.size}")

        if arr.size < self.size:
            padded = np.zeros(self.size, dtype=self.dtype)
            padded[:arr.size] = arr
            arr = padded

        if not np.array_equal(self.data, arr):
            with self.lock:
                with open(self.path, "wb") as f:
                    arr.tofile(f)
            self.data = arr