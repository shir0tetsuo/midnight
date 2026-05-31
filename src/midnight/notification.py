from typing import Optional, Literal
from .ansicodes import *
import textwrap

class Notification:
    def __init__(
            self, 
            s:Optional[str]=None, 
            t:int=6,
            expression:str='!' 
        ):
        '''
        :param s: The string to append to the ui elements buffer.
            Destroying `Notification.s` will destroy the notification.
        :type s: String
        :param t: Number of seconds to render the notification. 
            `-1` will render until cleared.
        :type t: Integer

        ---
        
        In `_render_...` pipeline:
        >>> ui_elements.append(
                self.Notification.ui_elements(
                    (self.rows, self.cols), self.yx_center)
                )
        '''
        self.s:Optional[str] = s
        self.expression = expression
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
            return (True if (self.s is not None) else False)
        is_displayed = (True if int(self.dt)<self.t else False)
        if is_displayed and (self.s is not None):
            return True
        else:
            self.s=None
            return False

    def ui_elements(self, yx:tuple[int,int], yx_center:tuple[int,int]):
        s=f'[{self.expression}] '+str(self.s)
        if len(s) > 200:
            s = s[:197]+'...'
        texts=textwrap.wrap(s, width=yx_center[1])
        _c=[]
        for i, line in list(enumerate(reversed(texts))):
                
            diff = yx[0] - 1 - i
            if i>0:
                _c.append((Cursor(diff, 2), line))
            else:
                _c.append((Cursor(diff, 2), REVERSEVIDEO, ' ', line))
        
        flat = []
        for item in _c:
            flat.extend(item)
        flat.extend((' ', RESETFORMATTING))
        return tuple(flat) 