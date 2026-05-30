main_keymap = {
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