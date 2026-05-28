import re

SAFE_RE = re.compile(r'^[^\x00-\x1F\x7F\u200B-\u200F\u202A-\u202E\u2060\uFEFF]+$')
def IS_VISUALLY_SAFE(s:str):
    return bool(SAFE_RE.fullmatch(s))



SPECIAL = {

}

