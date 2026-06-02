import numpy as np
from ._storage import Store
from typing import Union, Literal, Optional
import random
from .version import __version__
import os

# NOTE : May need optimization

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

    @property
    def _mantissa_bits(self):
        return 23 if self._bits == 32 else 52

    @property
    def _exponent_bits(self):
        return 8 if self._bits == 32 else 11

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
    
    def floating_to_mantissa(
            self,
            value: Union[np.float32, np.float64]
        ) -> np.ndarray:
        '''
        Extract mantissa bits from a floating-point value.

        Returns:
            np.ndarray[np.uint8]
            Length 23 (float32) or 52 (float64)
        '''
        bits = self.floating_to_bits(value)

        sign_bits = 1
        exponent_bits = self._exponent_bits

        return bits[sign_bits + exponent_bits:]


    def mantissa_to_floating(
            self,
            mantissa_bits: list[Union[int, bool]],
            sign: int = 0,
            exponent: Optional[list[Union[int, bool]]] = None
        ):
        '''
        Reconstruct a float from mantissa bits.

        By default uses exponent=0 and sign=0, producing
        a subnormal value.

        Parameters
        ----------
        mantissa_bits
            23 or 52 bits.
        sign
            0 or 1.
        exponent
            Exponent bit array. If None, all zeros.
        '''

        mantissa_len = self._mantissa_bits
        exponent_len = self._exponent_bits

        if len(mantissa_bits) != mantissa_len:
            raise ValueError(
                f"Expected {mantissa_len} mantissa bits, got {len(mantissa_bits)}"
            )

        if exponent is None:
            exponent = [0] * exponent_len

        if len(exponent) != exponent_len:
            raise ValueError(
                f"Expected {exponent_len} exponent bits, got {len(exponent)}"
            )

        full_bits = (
            [int(sign)]
            + [int(x) for x in exponent]
            + [int(x) for x in mantissa_bits]
        )

        return self.bits_to_floating(full_bits)
    
    def mantissa_to_bits(self, value):
        return self.floating_to_mantissa(value)

    def bits_to_mantissa(self, bits):
        return self.mantissa_to_floating(bits)

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
