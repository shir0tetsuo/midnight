from typing import Tuple, Literal, Optional, Union
from .ansicodes import *
from .buffer import Dynamic
import numpy as np

class Entity(Dynamic):

    def __init__(
            self, 
            yx: tuple[int,int] = (0,0),
            ID: int = 0,
            LVL:int = 1,
            HP: tuple[int,int] = (50,15),
            colors: Union[list[int], list[tuple[Optional[str],Optional[str]]]] = [17,18,19,20,21,63,105,111,147],
            chars: list[str] = ["@"],
            color_frequency: float = float(1/16),  # Transition delay
            char_frequency: float = float(1/8),    # Transition delay
        ):
        super().__init__(colors, chars, color_frequency, char_frequency)

        self.yx:Tuple[int,int]=yx   # Game world position
        self.ID:int=ID              # Game Entity ID
        self.LVL = LVL              # Game Entity Level

        # Health
        self._HP_aura, self._HP_core = HP

    @property 
    def as_kwargs(self):
        return  {
            'yx': self.yx,
            'ID': self.ID,
            'LVL': self.LVL,
            'HP': (self._HP_aura, self._HP_core)
        }
