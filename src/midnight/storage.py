import numpy as np
from pathlib import Path
import os
import threading
import platform
from typing import Union

class Store:
    _system = {}
    
    def __init__(
            self,
            identifier:str,
        ):
        '''
        :param identifier: The storage identifier (name of the file), no suffix.
        '''
        self.lock = threading.RLock()

        # Get system, path
        self._system.setdefault('system', platform.system())
        self.basepath = self.get_basepath()
        self.path:Path = self.basepath / f'{identifier}.bin'
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
    def system(self):
        return self._system.get('system', 'Unknown')
    
    @property
    def exists(self):
        return self.path.exists()

class BitStore(Store):

    @staticmethod
    def is_divisible_by_8(n: int) -> bool:
        return n % 8 == 0

    @staticmethod
    def schema_to_dict(bs:list[tuple[str|int, int]]):
        fields = {}
        for identifier, num_bits in bs:
            fields[identifier] = {'bits': num_bits, 'value': 0}
        return fields

    def __init__(
            self,
            identifier: str,
            bitschema:list[tuple[int|str, int]] = [
                ("a", 2),
                ("b", 2),
                ("c", 2),
                ("d", 2)
            ]
        ):

        super().__init__(identifier=identifier)
    
        self.total_bits = sum(bits for _, bits in bitschema)
        if not BitStore.is_divisible_by_8(self.total_bits):
            raise ValueError('Schema is not divisible by 8 (byte).')
        
        self.data:dict[int|str, dict[str, int]] = BitStore.schema_to_dict(bitschema)

        pass

    def read(self):
        if not self.exists:
            return
        
        with self.lock:
            with open(self.path, 'rb') as f:
                byte_data = f.read()
        
        # Convert bytes to integer (big-endian)
        value = int.from_bytes(byte_data, byteorder='big')
        
        # Extract each bit field and assign to self.data
        offset = self.total_bits
        for identifier, field_info in self.data.items():
            num_bits = field_info['bits']
            offset -= num_bits
            # Extract bits from position offset to offset+num_bits
            mask = (1 << num_bits) - 1
            extracted_value = (value >> offset) & mask
            self.data[identifier]['value'] = extracted_value

    def write(self):
        value = 0
        offset = self.total_bits
        
        # Pack bit fields into a single integer
        for identifier, field_info in self.data.items():
            num_bits = field_info['bits']
            offset -= num_bits
            field_value = field_info['value']
            # Ensure value fits in the bit width
            mask = (1 << num_bits) - 1
            field_value = field_value & mask
            # Shift and combine
            value |= (field_value << offset)
        
        # Convert to bytes
        num_bytes = self.total_bits // 8
        byte_data = value.to_bytes(num_bytes, byteorder='big')
        
        # Write to file with thread safety
        with self.lock:
            with open(self.path, 'wb') as f:
                f.write(byte_data)


class BinStore(Store):
    '''Store numpy arrays of numpy floats into binary files.'''

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
        '''
        :param identifier: The storage identifier (name of the file), no suffix.
        :param size: Maximum size of chunks to read. The file will be padded to
            **`n`**`*dtype*size`
        '''

        super().__init__(identifier=identifier)

        # Maximum float store size
        self.dtype = dtype
        self.size  = size
        self.data  = None

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