from typing import Optional, Literal
import sys
import shutil

ALTSCR_ENABLE   = '\033[?1049h'  # Enable alt. screen (prevents scroll corruption)
ALTSCR_DISABLE  = '\033[?1049l'
CLEAR           ='\033[2J'
HIDECURSOR      ='\033[?25l'
SHOWCURSOR      ='\033[?25h'
CLEARLINE       ='\033[2K'
RESETFORMATTING ='\033[0m'
REVERSEVIDEO    ='\033[7m'
CURSORTOTOPLEFT ='\033[H'

BOLD      = '\033[1m'
DIM       = '\033[2m'
ITALIC    = '\033[3m'
UNDERLINE = '\033[4m'
BLINK     = '\033[5m'

def TerminalSize():
    s = shutil.get_terminal_size()
    return s.lines, s.columns

def CursorRelative(
        direction :Literal['up','down','right','left'], 
        distance  :int
    ):
    d = {
        'up': 'A',
        'down': 'B',
        'right': 'C',
        'left': 'D' 
    }[direction]
    if distance <=0: distance = 1
    return f'\033[{distance}{d}'


def Cursor(y_row: int, x_col: int):
    if y_row <=0: y_row = 1
    if x_col <=0: x_col = 1
    return f'\033[{y_row};{x_col}H'

def SimpleColor(color_code: int):
    return f"\033[38;5;${color_code}m"

def Color(
        text: Optional[str] = None, 
        fg_hex: Optional[str] = None, 
        bg_hex: Optional[str] = None, 
        reset: bool = True,
        color_only: bool = False
    ) -> str:
    '''
    Return text formatted with ANSI truecolor codes using hex colors.

    :param text:
        Text to print.
    fg_hex : str
        Foreground hex color (#RRGGBB).
    bg_hex : str
        Background hex color (#RRGGBB).
    reset : bool
        Reset terminal color after text.
    '''
    import re

    def hex_to_rgb(h):
        h = h.lstrip('#')
        if not re.fullmatch(r"[0-9a-fA-F]{6}", h):
            raise ValueError(f"Invalid hex color: {h}")
        return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

    codes = []

    if fg_hex:
        r, g, b = hex_to_rgb(fg_hex)
        codes.append(f"\033[38;2;{r};{g};{b}m")

    if bg_hex:
        r, g, b = hex_to_rgb(bg_hex)
        codes.append(f"\033[48;2;{r};{g};{b}m")

    start = "".join(codes)

    if color_only:
        return start

    end = RESETFORMATTING if reset else ""

    return f"{start}{text}{end}"

def ClearToEnd(direction:Literal['end', 'beginning', 'screen']):
    d = {
        'end': 0,
        'beginning': 1,
        'screen': 2 
    }[direction]
    return f"\033[{d}J"

def ClearToEndLine(direction:Literal['end', 'beginning', 'line']):
    d = {
        'end': 0,
        'beginning': 1,
        'line': 2 
    }[direction]
    return f"\033[{d}K"

def Write(*parts):
    # Write(Cursor(10,10), "@")
    sys.stdout.write("".join(map(str, parts)))

def Flush():
    sys.stdout.flush()