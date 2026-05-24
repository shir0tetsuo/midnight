# compatibility.py
import os
import sys
import subprocess
import platform


def ensure_utf8_locale():
    '''
    Ensures UTF-8 compatibility for terminal applications.
    Works by adjusting environment variables BEFORE app execution.
    '''

    system = platform.system()

    # Linux / macOS

    if system in ("Linux", "Darwin"):
        os.environ.setdefault("LANG", "en_US.UTF-8")
        os.environ.setdefault("LC_ALL", "en_US.UTF-8")

        # Also ensure Python itself uses UTF-8 I/O
        os.environ.setdefault("PYTHONIOENCODING", "utf-8")


    # Windows

    elif system == "Windows":
        # Modern Windows terminals already support UTF-8
        # but Python needs explicit encoding hint sometimes

        os.environ.setdefault("PYTHONIOENCODING", "utf-8")

        # Force UTF-8 mode for Python (very important)
        os.environ["PYTHONUTF8"] = "1"

        # Optional: try to switch code page (best effort only)
        try:
            os.system("chcp 65001 > nul")
        except Exception:
            pass


def relaunch_with_utf8():
    '''
    Relaunches the current process with UTF-8-safe environment if needed.
    Prevents partial or inconsistent encoding states.
    '''

    system = platform.system()

    env = os.environ.copy()

    if system in ("Linux", "Darwin"):
        env.setdefault("LANG", "en_US.UTF-8")
        env.setdefault("LC_ALL", "en_US.UTF-8")

    elif system == "Windows":
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"

    # Re-run the same Python process
    subprocess.run([sys.executable] + sys.argv, env=env)
    sys.exit(0)

# Lightweight, Safe
def setup_utf8():
    system = platform.system()

    if system in ("Linux", "Darwin"):
        os.environ.setdefault("LANG", "en_US.UTF-8")
        os.environ.setdefault("LC_ALL", "en_US.UTF-8")

    elif system == "Windows":
        os.environ.setdefault("PYTHONUTF8", "1")
        os.environ.setdefault("PYTHONIOENCODING", "utf-8")

if __name__ == "__main__":
    ensure_utf8_locale()