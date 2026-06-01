from pathlib import Path

def maps_directory():
    if "__file__" in globals():
        return Path(__file__).resolve().parent
    else:
        raise RuntimeError('Maps: __file__ not in globals')