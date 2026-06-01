from typing import Optional, Literal, Union
from .ansicodes import Write, RESETFORMATTING
import re

class Dynamic:

    def __init__(
            self,
            colors: Union[list[int], list[tuple[Optional[str],Optional[str]]]] = [17,18,19,20,21,63,105,111,147],
            chars: list[str] = ["@"],
            color_frequency: float = float(1/16),  # Transition delay
            char_frequency: float = float(1/8),    # Transition delay
        ):
        '''
        :param colors: The terminal color panel to cycle through
        :type colors: `list[int]` or `list[tuple[Optional[str], Optional[str]]]`
        :param chars: The terminal characters panel to cycle through
        :type chars: `list[str]` (Single Characters)
        :param color_frequency: The float value of the transition delay for color cycle
        :param char_frequency: The float value of the transition delay for characters
        '''

        # Direct is by the single integer; Mixed uses tuples through Color
        self._colormode = 'Direct' if isinstance(colors, list[int]) else 'Mixed'
        self._frq_color = color_frequency
        self._frq_chars = char_frequency
        self._chars:list[str] = chars
        # Build a palindromic color list by appending the reversed
        self._colors:Union[list[int], list[tuple[Optional[str],Optional[str]]]] = colors + colors[:-1][::-1]

    def _color(self, dt:float):
        if self._colormode == 'Direct':
            c=self._colors[int(dt % self._frq_color) % len(self._colors)]
            t=f"\033[38;5;${c}m"
            # t=f"\e[38;5;${c}m"
            return t
        elif self._colormode == 'Mixed':
            fg,bg=self._colors[int(dt % self._frq_color) % len(self._colors)]
            codes = []
            for i,h in list(enumerate([fg,bg])):
                h=h.lstrip('#')
                if not re.fullmatch(r"[0-9a-fA-F]{6}", h):
                    raise ValueError(f"Invalid hex color: {h}")
                r,g,b=tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
                codes.append(f"\033[{38 if i==0 else 48};2;{r};{g};{b}m")
            t="".join(codes)
            return t
    
    def _character(self, dt:float, additional_chars:Optional[list[str]]=None):
        if additional_chars is not None:
            _c=self._chars+additional_chars
            return _c[int(dt % self._frq_chars) % len(self._colors)]
        return self._chars[int(dt % self._frq_chars) % len(self._colors)]
    
    def to_buffer(self, dt:float, additional_chars:Optional[list[str]]=None):
        '''Combined color + character for buffer'''
        color = self._color(dt)
        char = self._character(dt, additional_chars)
        return f'{color}{char}{RESETFORMATTING}'


class TerminalBuffer:
    def __init__(self):
        self.primary    :list[tuple]            = []    # Actual elements to render on terminal
        self.diffcheck  :Optional[list[tuple]]  = None

    @property
    def is_different(self):
        '''
        Check whether or not the buffer differs
        from the last render, therefore not rendering
        everything over again if there are no differences,
        huge savings for 60 FPS where a frame may only truly update
        once every 1-2 seconds.
        '''
        return (self.diffcheck or []) != self.primary
    
    def flush(self):
        '''
        Flush primary elements to the terminal
        sequentially using `Write(*parts)`,
        Effectively the same as `sys.stdout.write("".join(map(str, parts)))`
        '''
        # Copy primary elements to diff check,
        # when the diff
        self.diffcheck = self.primary.copy()
        for element in self.primary:
            Write(*element)