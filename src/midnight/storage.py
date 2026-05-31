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
    
class Log(Store):
    def __init__(self, identifier):
        super().__init__(identifier, suffix='.log')
        # Configure a dedicated logger that writes to this log file.
        # Use the file path as part of the logger name so multiple
        # Log instances don't clash.
        logger_name = f"midnight.log.{identifier}"
        self.logger = logging.getLogger(logger_name)
        # Avoid adding multiple handlers if logger already configured
        if not any(isinstance(h, logging.FileHandler) and getattr(h, 'baseFilename', '') == str(self.path) for h in self.logger.handlers):
            fh = logging.FileHandler(str(self.path), encoding='utf-8')
            fh.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s'))
            self.logger.addHandler(fh)
            self.logger.setLevel(logging.INFO)
            self.logger.propagate = False

    def Tee(self, *args, level: str = 'info', sep: str = ' ', end: str = '\n', **kwargs):
        """Print like `print()` and also log the same message to the file.

        Parameters:
        - *args: values to be printed/logged (joined by `sep`).
        - level: logging level to use (info, debug, warning, error, critical).
        - sep, end, flush: same semantics as `print()`.
        - **kwargs: additional keyword args forwarded to `print()`.
        """
        # Format the message
        msg = sep.join(str(a) for a in args)

        # Log to file using configured logger
        if hasattr(self, 'logger') and self.logger is not None:
            level_name = (level or 'info').lower()
            log_method = getattr(self.logger, level_name, self.logger.info)
            try:
                log_method(msg)
            except Exception:
                # If logging fails for any reason, fall back to writing bytes
                try:
                    with open(self.path, 'a', encoding='utf-8') as f:
                        f.write(msg + (end or '\n'))
                except Exception:
                    pass

class SaveFile(Store):

    # NOTE : 3.4e38 (32-bit), 256*256
    #        = 256 KB / file,
    #        more than enough values

    HEADER_SIZE = 128
    cast:dict[str, tuple[int, Union[np.float32, np.float64], int, Union[np.uint32, np.uint64]]] = {
        '32-bit': (
            65536-(HEADER_SIZE // np.dtype(np.float32).itemsize), 
            np.float32, 32, np.uint32
        ),
        '64-bit': (
            32768-(HEADER_SIZE // np.dtype(np.float64).itemsize), 
            np.float64, 64, np.uint64
        )
    }
    _max_float32 = np.finfo(np.float32).max
    _max_float64 = np.finfo(np.float64).max

    @staticmethod
    def random_float(num_bit:Optional[Literal['32-bit', '64-bit']] = '32-bit'):
        value = random.random() * (
            SaveFile._max_float32 if num_bit=='32-bit'
            else SaveFile._max_float64 if num_bit == '64-bit'
            else SaveFile._max_float32
        )
        return value

    def __init__(
            self, 
            identifier,
            store_type: Literal['32-bit', '64-bit'] = '32-bit'
        ):
        super().__init__(identifier, suffix='.bin')
        
        self.store_type = store_type

        # size, dtype, bits, uint
        self._size, self._dtype, self._bits, self._uint = self.cast[self.store_type]
        self._bit_shifts = np.arange(self._bits - 1, -1, -1, dtype=np.int32)
        self.data = self._open_memmap()

    @property
    def header(self):
        h = (
            b"MID.NIGHTMOONBEAM_" 
            + __version__.encode("utf-8") 
            + b'_' 
            + self.store_type.encode("utf-8")
        )
        return h.ljust(self.HEADER_SIZE, b"\x00")

    def _open_memmap(self):

        expected_size = (
            self.HEADER_SIZE +
            self._size * np.dtype(self._dtype).itemsize
        )

        with self.lock:
            if not self.exists:
                with open(self.path, "wb") as f:
                    f.write(self.header)
                    f.truncate(expected_size)

                data = np.memmap(
                    self.path,
                    dtype=self._dtype,
                    mode="r+",
                    offset=self.HEADER_SIZE,
                    shape=(self._size,)
                )

                data.flush()

                return data

            # Validate existing file

            actual_size = self.size_bytes
            if actual_size != expected_size:
                raise ValueError(
                    f"Invalid file size: expected {expected_size}, got {actual_size}"
                )

            with open(self.path, "rb") as f:
                header = f.read(self.HEADER_SIZE)

            decoded = header.decode("utf-8", errors="replace").rstrip("\x00")

            # Fast prefix check (cheap reject)
            if not header.startswith(b"MID.NIGHTMOONBEAM_"):
                raise ValueError(f"Bad header magic: {decoded}")

            # Structured parse (safe + stable)
            parts = decoded.split("_")
            if len(parts) < 3:
                raise ValueError("Corrupt header (invalid format)")

            _, version, dtype_tag = parts[:3]

            if dtype_tag != self.store_type:
                raise TypeError(
                    f"Store type mismatch: expected {self.store_type}, got {dtype_tag}"
                )

            return np.memmap(
                self.path,
                dtype=self._dtype,
                mode="r+",
                offset=self.HEADER_SIZE,
                shape=(self._size,)
            )

    def value_cast(
            self, 
            value:Union[
                int, float, bool, np.integer, np.floating, np.bool_
            ]
        ) -> Union[np.float32, np.float64]:
        if isinstance(value, self._dtype):
            return value
        cv = self._dtype(value)
        return cv if np.isfinite(cv) else (_ for _ in ()).throw(ValueError(f"Cannot align value to {self._dtype}: {value}"))
        
    def poke(
            self, index:int, value:Union[
                int, float, bool, np.integer, np.floating, np.bool_
            ]
        ):
        if not (0 <= index < self._size):
            raise IndexError(
                f"Index {index} out of range [0, {self._size}]"
            )
        # NOTE : Index can be expressed like 
        # (32*32) up to 128 (64) / 256 (32)
        self.data[index] = self.value_cast(value)

    def floating_to_bits(self, value: Union[np.float32, np.float64]):
        f = np.asarray(value, dtype=self._dtype)
        as_int = f.view(self._uint)
        return ((as_int >> self._bit_shifts) & 1).astype(np.uint8)
        # return ((as_int >> np.arange(self._bits - 1, -1, -1)) & 1).astype(np.uint8)
    
    def bits_to_floating(self, bits: list[Union[int, bool]]):
        max_bits, uint = self._bits, self._uint
        if len(bits) != max_bits:
            raise ValueError(f"Must be exactly {max_bits}")
        as_int = 0
        for b in bits:
            as_int = (as_int << 1) | int(b)
        
        return uint(as_int).view(self._dtype)

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
