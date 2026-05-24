import numpy as np
from pathlib import Path
import os
import threading
import platform

class BinStore:
    '''Store numpy arrays of float32 into binary files.'''

    _system = {}

    def __init__(
            self, 
            identifier:str,
            size: int = 512  # Maximum size of float32 chunks to read
        ):

        self.lock = threading.RLock()
        # Get system, path
        self.system = self._system.setdefault('system', platform.system())
        self.basepath = self.get_basepath()
        self.path = self.basepath / identifier + '.bin'
        self.size = size

        pass

    @property
    def system(self):
        return self.system.get('system', 'Unknown')

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
    
    def load(self):

        with self.lock:
            with open(self.path, "rb") as f:
                loaded = np.fromfile(f, dtype=np.float32, count=self.size)

        return loaded
    
    # data = np.array([1.0, 2.0, 3.0, 4.0, 5.0], dtype=np.float32)
    def write(self, arr: np.ndarray):
        arr = np.asarray(arr, dtype=np.float32).ravel()

        if arr.size > self.size:
            raise ValueError(f"Expected {self.size} elements, got {arr.size}")

        if arr.size < self.size:
            padded = np.zeros(self.size, dtype=np.float32)
            padded[:arr.size] = arr
            arr = padded

        with self.lock:
            with open(self.path, "wb") as f:
                arr.tofile(f)
