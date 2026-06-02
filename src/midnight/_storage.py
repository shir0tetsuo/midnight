import numpy as np
from pathlib import Path
import os
import threading
import platform
from typing import Union, Optional, Literal
import logging
import random
from .version import __version__

class Store:
    '''Primary source of save directory information'''
    _system = {}
    
    def __init__(
            self,
            identifier:str,
            suffix: str = '.bin'
        ):
        '''
        :param identifier: The storage identifier (name of the file), no suffix.
        '''
        self.lock = threading.RLock()
        self.suffix = suffix

        # Get system, path
        self._system.setdefault('system', platform.system())
        self.basepath = self.get_basepath()
        self.path:Path = self.basepath / f'{identifier}{suffix}'
        # pass

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
    
    @property
    def size_bytes(self):
        try:
            return self.path.stat().st_size
        except (FileNotFoundError, OSError):
            return 0

    @property
    def human_size_bytes(self) -> Optional[str]:
        size = self.size_bytes
        for unit in ("B", "KB", "MB", "GB"):
            if size < 1024 or unit == "PB":
                return f"{size:.1f} {unit}"
            size /= 1024
        return

    @property
    def system(self):
        return self._system.get('system', 'Unknown')
    
    @property
    def exists(self):
        return self.path.exists()