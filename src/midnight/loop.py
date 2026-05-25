import curses
import time
import traceback
from .storage import BinStore
from .bootstrap import initialize
from typing import Union
import numpy as np

class GameLoop:
    def __init__(self, stdscr: curses.window):
        self.stdscr = stdscr
        self.running = True
        self.gamestate = "MAINMENU"

        # item/entity buffers
        self.menuobjects = []
        self.itembuf = []
        self.entities = []

        self.rows, self.cols = self._update_yx()

        self.KEYSETTINGS = BinStore('keysettings', dtype=np.float16, size=6)
        if not self.KEYSETTINGS.exists:
            self.KEYSETTINGS.write(
                self.KEYSETTINGS.formatted(
                    [   # UP, DOWN, LEFT, RIGHT, ENTER (A), BACKSPACE (B)
                        curses.KEY_UP,
                        curses.KEY_DOWN,
                        curses.KEY_LEFT,
                        curses.KEY_RIGHT,
                        curses.KEY_ENTER,
                        curses.KEY_BACKSPACE
                    ]
                )
            )
        


    # ---- This wraps curses window around new GameLoop instance ----
    @staticmethod
    def _loop_start(stdscr: curses.window):
        game = GameLoop(stdscr)
        game.run()

    @staticmethod
    def start():
        initialize()
        curses.wrapper(GameLoop._loop_start)
    # ---------------------------------------------------------------

    # Quick check in keys for unicode key ord
    @staticmethod
    def _in_k(
            k_ord:Union[str, int, float], 
            keys:set[int]
        ):
        return (
            True if (
                ord(k_ord) if isinstance(k_ord, str) else int(k_ord)
            ) in keys 
            else False
        )

    # Terminal inputs iterator (call once)
    @property
    def _inputs(self):
        keys = set()
        while True:
            key = self.stdscr.getch()
            if key == -1:
                break
            keys.add(key)
        return keys
    
    def render(self):
        '''Render changes to screen'''

        return
    
    def _update_yx(self):
        '''Obtain `(rows, cols)` for terminal'''
        rows, cols = self.stdscr.getmaxyx()
        return rows, cols
    
    def update(self, dt:float):
        '''Update game objects'''
        self.rows, self.cols = self._update_yx()
        keys = self._inputs


        return
    
    def run(self):
        self.stdscr.nodelay(True)
        curses.curs_set(0)
        
        last = time.perf_counter()

        try:
            while self.running:
                now = time.perf_counter()
                dt = now - last  # delta time
                last = now

                self.update(dt)
                self.render()

                time.sleep(0.016)  # ~60 FPS

        except Exception as exc:
            self.running = False
            print(f"\n❌ {exc}")
            traceback.print_exc()
            raise