# from .util import (...)
from .compatibility import ensure_utf8_locale, setup_utf8
from .loop import GameLoop
from .storage import BinStore

try:
    from importlib.metadata import version
    __version__ = version("midnight")
except Exception:
    __version__ = "0.0.0"

__all__ = [
    "ensure_utf8_locale",
    "setup_utf8",

    "GameLoop",
    
    "BinStore"
]