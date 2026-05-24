import curses
import time
import traceback
from .bootstrap import initialize

class GameLoop:
    def __init__(self, stdscr: curses.window):
        self.stdscr = stdscr
        self.running = True
        self.gamestate = "MENU"
        self.rows, self.cols = self._update_yx()


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
            k_ord:str, 
            keys:set[int]
        ):
        return (
            True if ord(k_ord) in keys 
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
            print(f"\n❌ Error: {exc}")
            traceback.print_exc()
            raise