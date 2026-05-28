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
        self.bctl = bctl

        self.DELTAS = {'current_time': 0.0}

        # NOTE : UI Elements should be
        # the last to render
        self._ui_elements = None   # Check for diff
        self.ui_elements = []      # Actual UI element codes to render
        self._buffer = None        # Check for diff
        self.buffer = []           # Actual screen codes to render

        # initialize()  # UTF-8 and control code bootstrap
        self.rows, self.cols = self._yx()

    @staticmethod
    def _yx():
        s = shutil.get_terminal_size()
        return s.lines, s.columns
    
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

    def _update_top_bottom(self, timestamp:str):

        if timestamp is None:
            ts=datetime.fromtimestamp(time.time())
            timestamp = str(ts)

        # UPDATE Top/Bottom UI Elements
        ui_s = self.cols
        ui_top_text = (
            f" MIDNIGHT 0.0.0 {timestamp}"
        )
        ui_tt_s = len(ui_top_text)
        ui_top_diff_s = ui_s - ui_tt_s
        final_row = self.rows
        self.ui_elements = [
            (
                CURSORTOTOPLEFT,
                CLEARLINE,
                REVERSEVIDEO,
                ui_top_text,
                ' '*ui_top_diff_s
            ),
            (
                Cursor(final_row, 0),
                CLEARLINE,
                REVERSEVIDEO,
                ' Hello, World!'
            )
        ]
    
    def update(self, dt:float):
        # NOTE : Need to update the render
        # matrix here...
        self.rows, self.cols = self._yx()
        keys = self._input_poll()

        # CTRL-C = EXIT
        if ('CTRL_C' in keys):
            self.running = False
        
        if (self.DELTAS['current_time'] == 0) or (self.DELTAS['current_time'] % 1 == 0):
            ts=datetime.fromtimestamp(time.time())
            timestamp = str(ts)
        self.DELTAS['current_time'] += dt

        self._update_top_bottom(dt, timestamp)

            
        return
    
    def _render_MAINMENU(self):
        
        return
    
    def render(self):
        # NOTE : Flush to screen happens after.
        # Check the buffer; Iterate; Render.
        # No need to constantly redraw every frame.

        try:
            getattr(self, f'_render_{self.gamestate}')()
        except Exception as e:
            raise

        # TODO : Render scr elements

        # Write(
        #     CURSORTOTOPLEFT,
        #     Cursor(5, 5),
        #     "Hello, World!"
        # )


        # Render UI Elements
        if self._ui_elements is None:
            self._ui_elements = self.ui_elements
        if self._ui_elements != self.ui_elements:
            for ui_element in self.ui_elements:
                Write(ui_element)

            return Flush()
        
        # TODO : Flush for diff in render scr elements

        return  # Proceed without drawing
    
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
        
