import time
import traceback
from .storage import BinStore
from .bootstrap import bootctl
from .ansicodes import *
from .entity import Player
from typing import Union, Optional
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

    class _Notification:
        def __init__(self, s:Optional[str]=None, t:int=6):
            self.s:Optional[str] = s
            self.dt:float = None
            self.t = t
            pass
        
        def update(self, dt):
            if self.dt is None:
                self.dt = dt
            else:
                self.dt += dt

        @property
        def display(self):
            if self.t <= 0:  # -1 will render forever until cleared
                return True
            is_displayed = (True if int(self.dt)>=self.t else False)
            if is_displayed:
                return True
            else:
                self.s=None
                return False

        def ui_elements(self, yx:tuple[int,int], yx_center:tuple[int,int]):
            s='[!] '+str(self.s)
            if len(s) >= 200:
                s = s[:197]+'...'
            texts=textwrap.wrap(s, width=yx_center[1])
            lines = len(texts)-1
            _c=[]
            for i, line in list(enumerate(texts)):
                    
                diff = (yx[0])-lines-(i+1)
                if i>0:
                    _c.append((Cursor(diff, 2), line))
                else:
                    _c.append((Cursor(diff, 2), REVERSEVIDEO, ' ', line))

            return tuple(tuple(tup) for tup in _c) + (' ', RESETFORMATTING)

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
        b' ': 'SPACE',
        b'\t': 'TAB',
        b'\x1b': 'ESCAPE',

        b'q': 'Q',  # Exit (B)

        b'\x03': 'CTRL_C',
    }


    def __init__(self, bctl:bootctl):

        self.running = True             # False -> EXIT
        self.gamestate = "MAINMENU"     # Affects update, render calls
        self.start_frame = True         # If start frame, init top bar ui
        self.enter_pressed = False      # If ENTER is pressed -> action
        self.bctl = bctl                # Boot Control
        self.debugmode = False          # Special Debugging Flag
        self.Player:Optional[Player] = None

        self.ui_delta = 0.0     # Every int()+1 -> get time, update ui
        self.selected:tuple[int, int] = (0, 0)  # row, col selected in select screens

        # NOTE : UI Elements should be
        # the last to render
        self._ui_elements = None   # diff check
        self.ui_elements  = []     # Actual UI element codes to render
        self._buffer      = None   # diff check
        self.buffer       = []     # Actual SCREEN codes to render
        self.Notification = GameLoop._Notification()

        # self._uifootnote_t = 0.0
        # self._uifootnote_max = 6
        # self._uifootnote:Optional[str] = None

        self.rows, self.cols = self._yx()
        self._yx_center = None
        self._yx_quarter = None


    def _yx(self):
        s = shutil.get_terminal_size()
        rows, cols = s.lines, s.columns
        if hasattr(self, 'rows'):
            if (self.rows != rows) or (self.cols != cols):
                self._yx_center = int(rows/2)-1, int(cols/2)-1
                self._yx_quarter = int(rows/4), int(cols/4)
                Write(CLEAR)
        return s.lines, s.columns
    
    @property
    def yx_center(self):

        # Don't recalculate center unless needed
        if self._yx_center is not None:
            return self._yx_center
            
        self._yx_center = (int(self.rows/2)-1, int(self.cols/2)-1)
        return self._yx_center
    
    @property
    def yx_quarter(self):
        if self._yx_quarter is not None:
            return self._yx_quarter

        self._yx_quarter = (int(self.rows/4), int(self.cols/4))
        return self._yx_quarter
    
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
        '''Update the top UI bar with timestamp.'''

        if timestamp is None:
            ts=datetime.fromtimestamp(time.time())
            timestamp = str(ts)

        # UPDATE Top UI Elements
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
                ' '*(self.cols - len(ui_top_text) - len(ui_top_note)),
                ui_top_note,
                RESETFORMATTING
            )
        ]

    def normalize_selected(self, minimum:tuple[int, int], maximum:tuple[int, int]):
        sel_row, sel_col = self.selected

        cur_row = int(sel_row)
        cur_col = int(sel_col)

        if (cur_row < minimum[0]) or (cur_row > maximum[0]): cur_row = minimum[0]
        if (cur_col < minimum[1]) or (cur_col > maximum[1]): cur_col = minimum[1]

        if (cur_row != sel_row) or (cur_col != sel_col):
            self.selected = (cur_row, cur_col)
        
        return self.selected
    

    def _update_MAINMENU(self, keys:set[str]):
        
        # Enter unpress
        if len(keys) == 0:
            self.enter_pressed = False
            return
        
        # ---- UI SELECTION LOOP ----
        # (CURRENT SELECT STATE)
        s_row, s_col = self.selected
        # (INPUT)
        if ('LEFT' in keys):
            self.selected = (s_row, s_col-1)
        elif ('RIGHT' in keys):
            self.selected = (s_row, s_col+1)
        elif ('DOWN' in keys):
            self.selected = (s_row+1, s_col)
        elif ('UP' in keys):
            self.selected = (s_row-1, s_col)
        elif ('E' in keys) or ('ENTER' in keys) or ('SPACE' in keys):
            self.enter_pressed = True
        # (NORMALIZE)
        selected = self.normalize_selected((0,0),(2,1))
        
        if self.enter_pressed:
            state = {
                (0,0): 'CONTINUE', (0,1): 'NEWGAME',
                (1,0): 'SETTINGS', (1,1): 'SETTINGS',
                (2,0): 'BUILD',    (2,1): 'DEBUGMODE_TOGGLE'
            }
            gamestate = state.get(selected)
            if gamestate:
                self.gamestate = gamestate

        return
    
    def update(self, dt:float):
        '''
        Poll for rows, cols, inputs;
        Execute gamestate render
        '''
        # NOTE : Need to update the render
        # matrix here...

        # Obtain state data
        self.rows, self.cols = self._yx()
        keys = self._input_poll()

        # CTRL-C = EXIT ---------
        if ('CTRL_C' in keys):
            self.running = False
        # -----------------------

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
        # NOTE : Pass keys to gamestate updater
        # _update_NAMEOFGAMESTATE(keys)->None
        updater = getattr(self, f'_update_{self.gamestate}')
        if updater:
            updater(keys)
        # 
        # -------------------------------------------
        # NOTE : Update notification display timer
        self.Notification.update(dt)

        # NOTE : Clearing screen is always flashy.
        #        Try to avoid it!

        return
    
    def _render_DEBUGMODE_TOGGLE(self):
        self.debugmode = (False if self.debugmode else True)
        self.gamestate = 'MAINMENU'
        return False

    def _render_MAINMENU(self):

        if self.Notification.display:
            self.ui_elements.append(self.Notification.ui_elements((self.rows, self.cols), self.yx_center))

        default_sel = ' -------- '

        # NOTE : ui_elements do its own flushing.
        line1 = {
            (0,0): ' (1/2) CONTINUE / NEW GAME ',  # should be conditional
            (0,1): ' (2/2) NEW GAME '
        }.get(self.selected, default_sel)
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
            (1,0): ' (1/1) SETTINGS ',
            (1,1): ' (1/1) SETTINGS '
        }.get(self.selected, default_sel)
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
            (2,0): ' (1/2) BUILD ',
            (2,1): (f' (2/2) [{('X' if self.debugmode else ' ')}] DEBUG ')
        }.get(self.selected, default_sel)
        self.ui_elements.append(
            (
                Cursor(5,2),
                REVERSEVIDEO,
                CLEARLINE,
                line3,
                RESETFORMATTING
            )
        )

        line4 = ' [ENTER/SPACE] SELECT '
        self.ui_elements.append(
            (
                # Make sure Line 2 is clear
                Cursor(2, 0),
                CLEARLINE,

                Cursor(self.rows-2, 1),
                CLEARLINE,
                Cursor(self.rows-1, 2),  # max here later
                BOLD,
                REVERSEVIDEO,
                line4,
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
    

    # --- TO RUN THIS APPLICATION ---

    def _run(self):
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
        
        try: # Run main application
            with bootctl() as bctl: 
                GameLoop(bctl)._run()
        
        except Exception as exc:
            print(exc)
            traceback.print_exc()