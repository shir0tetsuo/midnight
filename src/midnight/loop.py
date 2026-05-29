import time
import traceback
from .storage import BinStore
from .bootstrap import bootctl
from .ansicodes import *
from typing import Union
import numpy as np
import textwrap
import shutil
import sys
import atexit
import termios
from datetime import datetime
import signal
import os
import select


class GameLoop:

    KEYMAP = {
        b'\x1b[A': 'UP',
        b'\x1b[B': 'DOWN',
        b'\x1b[C': 'RIGHT',
        b'\x1b[D': 'LEFT',

        b'\r': 'ENTER', # Interact (A)
        b'\x7f': 'BACKSPACE', # Exit (B)
        b'\x1b': 'ESC',

        b'w': 'W',  # UP
        b'a': 'A',  # LEFT
        b's': 'S',  # DOWN
        b'd': 'D',  # RIGHT
        b'e': 'E',  # Interact (A)

        b'q': 'Q',  # Exit (B)

        b'\x03': 'CTRL_C',
    }


    def __init__(self, bctl:bootctl):

        self.running = True
        self.gamestate = "MAINMENU"
        self.start_frame = True
        self.bctl = bctl

        self.ui_delta = 0.0     # Every int()+1 -> get time, update ui
        self.selected:tuple[int, int] = (0, 0)  # row, col selected in select screens

        # NOTE : UI Elements should be
        # the last to render
        self._ui_elements = None   # diff check
        self.ui_elements  = []     # Actual UI element codes to render
        self._buffer      = None   # diff check
        self.buffer       = []     # Actual SCREEN codes to render

        self.rows, self.cols = self._yx()
        self._yx_center = None


    def _yx(self):
        s = shutil.get_terminal_size()
        rows, cols = s.lines, s.columns
        if hasattr(self, 'rows'):
            if (self.rows != rows) or (self.cols != cols):
                self._yx_center = int(rows/2)-1, int(cols/2)-1
                Write(CLEAR)
        return s.lines, s.columns
    
    @property
    def yx_center(self):

        # Don't recalculate center unless needed
        if self._yx_center is not None:
            return self._yx_center
            
        self._yx_center = (int(self.rows/2)-1, int(self.cols/2)-1)
        return self._yx_center
    
    def _input_poll(self) -> set[str]:

        keys = set()

        while True:

            ready, _, _ = select.select(
                [sys.stdin],
                [],
                [],
                0
            )

            if not ready:
                break

            data = os.read(self.bctl.fd, 32)

            if not data:
                break

            if data in GameLoop.KEYMAP:
                keys.add(GameLoop.KEYMAP[data])

            else:
                keys.add(repr(data))

        return keys

    def _update_ui_bar(self, timestamp:str):

        if timestamp is None:
            ts=datetime.fromtimestamp(time.time())
            timestamp = str(ts)

        # UPDATE Top/Bottom UI Elements
        ui_s = self.cols
        ui_top_note = ' CTRL-C : QUIT '
        ui_top_text = (
            f" MIDNIGHT 0.0.0 {timestamp}"
        )[:(self.cols-1-len(ui_top_note))]

        self.ui_elements = [
            (
                CURSORTOTOPLEFT,
                CLEARLINE,
                REVERSEVIDEO,
                ui_top_text,
                ' '*(ui_s - len(ui_top_text) - len(ui_top_note)),
                ui_top_note,
                RESETFORMATTING
            )
        ]

    def _update_MAINMENU(self, keys:set[str]):
        
        if len(keys) == 0:
            return
        
        s_row, s_col = self.selected

        # NOTE : do s_row, s_col checking later,
        # just handle input here.
        if ('LEFT' in keys):
            self.selected = (s_row, s_col-1)
        elif ('RIGHT' in keys):
            self.selected = (s_row, s_col+1)
        elif ('DOWN' in keys):
            self.selected = (s_row+1, s_col)
        elif ('UP' in keys):
            self.selected = (s_row-1, s_col)
        
        return
    
    def update(self, dt:float):
        # NOTE : Need to update the render
        # matrix here...
        self.rows, self.cols = self._yx()
        keys = self._input_poll()

        # CTRL-C = EXIT
        if ('CTRL_C' in keys):
            self.running = False

        # Every 1/60 frames; Get timestamp, update UI
        prev = int(self.ui_delta)
        self.ui_delta += dt
        curr = int(self.ui_delta)
        if (prev != curr) or self.start_frame:
            # do expensive timestamp calculation once a second instead of 60/s
            ts=datetime.fromtimestamp(time.time())
            timestamp = str(ts)
            self._update_ui_bar(timestamp)
            if self.start_frame:
                self.start_frame = False
        # -------------------------------------------

        # Pass keys to gamestate updater
        updater = getattr(self, f'_update_{self.gamestate}')
        if updater:
            updater(keys)
            
        return
    
    
    def _render_MAINMENU(self):

        sel_row, sel_col = self.selected
        cur_row = int(sel_row)
        cur_col = int(sel_col)

        if (cur_row < 0) or (cur_row > 2): cur_row = 0
        if (cur_col < 0) or (cur_col > 1): cur_col = 0

        if (cur_row != sel_row) or (cur_col != sel_col):
            self.selected = (cur_row, cur_col)

        line1 = {
            (0,0): ' CONTINUE -> ',  # should be conditional
            (0,1): ' NEW GAME '
        }.get(self.selected, ' -------- ')
        self.ui_elements.append(
            (
                Cursor(3, 2),
                REVERSEVIDEO,
                CLEARLINE,
                line1,
                RESETFORMATTING
            )
        )

        line2 = {
            (1,0): ' SETTINGS ',
            (1,1): ' SETTINGS '
        }.get(self.selected, ' -------- ')
        self.ui_elements.append(
            (
                Cursor(4, 2),
                REVERSEVIDEO,
                CLEARLINE,
                line2,
                RESETFORMATTING
            )
        )

        line3 = {
            (2,0): ' GITHUB ',
            (2,1): ' DEBUG MODE '
        }.get(self.selected, ' -------- ')
        self.ui_elements.append(
            (
                Cursor(5,2),
                REVERSEVIDEO,
                CLEARLINE,
                line3,
                RESETFORMATTING
            )
        )
        return False

    def _ruiel(self):
        '''Render UI Elements with Write'''
        self._ui_elements = self.ui_elements.copy()
        for ui_element in self.ui_elements:
            Write(*ui_element)
        # TODO : Flush for diff in render scr elements
        return
    

    # ---- PRIMARY RENDER CONTROLLER ----
    def render(self):
        # NOTE : Flush to screen happens after.
        # Check the buffer; Iterate; Render.
        # No need to constantly redraw every frame.

        center_row, center_col = self.yx_center

        # Throw error for bad center;
        # Bad terminal size should crash the game.
        if (center_row <= 1) or (center_col <= 1):
            raise RuntimeError('Terminal size cannot support render.')

        do_flush = False

        # Run the main renderer per game state
        try:
            do_flush = bool(getattr(self, f'_render_{self.gamestate}')())
        except Exception:
            raise

        # Render UI Elements
        if (sorted((self._ui_elements or [])) != sorted(self.ui_elements)) or do_flush:
            self._ruiel()
            do_flush = True
            
        return (Flush() if do_flush else None)  # Proceed without drawing
    

    
    def run(self):
        last = time.perf_counter()
        try:
            while self.running:
                now = time.perf_counter()
                dt = now - last  # delta time
                last = now

                self.update(dt)
                self.render()

                time.sleep(0.016)  # ~60 FPS

        # Main Exception Traceback
        except Exception as exc:
            self.running = False
            print(f"\n❌ {exc}")
            traceback.print_exc()
            raise

        return
    
    @staticmethod
    def start():
        '''Execute run loop.'''
        try:
            with bootctl() as bctl:
                GameLoop(bctl).run()
        except Exception as exc:
            print(exc)
            traceback.print_exc()
        # exit() -> reset formatting


# class GameLoop:
#     def __init__(self, stdscr: curses.window):
#         self.stdscr = stdscr            # Curses Window
#         self.running = True             # If running=True, the game loop will continue
#         self.gamestate = "MAINMENUx"     # Defines render state

#         # This enables UP, DOWN, LEFT, and RIGHT keys on keypad
#         self.stdscr.keypad(True)

#         # item/entity buffers
#         # self.menuobjects = []
#         # self.itembuf = []
#         # self.entities = []

#         self.rows, self.cols = self._update_yx()  # Performs `self.stdscr.getmaxyx()` init

#         # ---- Obtain key settings ----
#         self.KEYSETTINGS = BinStore('keysettings', dtype=np.float16, size=6)
#         if not self.KEYSETTINGS.exists:
#             self.KEYSETTINGS.write(
#                 self.KEYSETTINGS.formatted(
#                     [   # UP, DOWN, LEFT, RIGHT, ENTER (A), BACKSPACE (B)
#                         curses.KEY_UP,
#                         curses.KEY_DOWN,
#                         curses.KEY_LEFT,
#                         curses.KEY_RIGHT,
#                         curses.KEY_ENTER,
#                         curses.KEY_BACKSPACE
#                     ]
#                 )
#             )
        
