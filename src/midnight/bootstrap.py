from .compatibility import setup_utf8
from .ansicodes import *
import sys
import tty
import termios
import signal

class bootctl:

    def __init__(self):
        self._cleaned = False
        self.old_sigint = None
        self.old_sigterm = None

        setup_utf8()

        self.fd = sys.stdin.fileno()
        self.old_termios = None

    def __enter__(self):

        # Without this, terminal may crash
        self.old_sigint = signal.getsignal(signal.SIGINT)
        self.old_sigterm = signal.getsignal(signal.SIGTERM)

        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        # Without this, terminal can become
        # stuck/broken, no echo, weird chars etc.
        self.old_termios = termios.tcgetattr(self.fd)

        # NOTE : Disables Ctrl-Z, Ctrl-C, flow control
        tty.setraw(self.fd)
        # immediate input, but terminal signals still work
        # tty.setcbreak(self.fd)

        Write(
            ALTSCR_ENABLE,
            HIDECURSOR,
            CLEAR,
            CURSORTOTOPLEFT
        )
        Flush()

        return self
    
    def _signal_handler(self, sig, frame):

        self._restore_terminal()

        raise KeyboardInterrupt
    
    def _restore_terminal(self):
        
        if self._cleaned:
            return

        self._cleaned = True

        try:
            signal.signal(signal.SIGINT, self.old_sigint)
            signal.signal(signal.SIGTERM, self.old_sigterm)

            if self.old_termios:

                termios.tcsetattr(
                    self.fd,
                    termios.TCSADRAIN,
                    self.old_termios
                )

            Write(
                RESETFORMATTING,
                SHOWCURSOR,
                ALTSCR_DISABLE
            )

            Flush()

        except Exception:
            pass

        return

    def __exit__(self, exc_type, exc, tb):
        self._restore_terminal()