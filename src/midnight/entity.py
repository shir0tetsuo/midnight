from typing import Tuple, Literal, Optional
from .storage import SaveFile
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
            colors = ..., chars = ..., color_frequency = ..., char_frequency = ...
        ):
        super().__init__(colors, chars, color_frequency, char_frequency)

        self.yx:Tuple[int,int]=yx   # Game world position
        self.ID:int=ID              # Game Entity ID
        self.LVL = LVL              # Game Entity Level

        # Health
        self._HP_aura, self._HP_core = HP

#     @property
#     def debug(self):
#         return {
#             'yx':self.yx,'name':self.name,
#             'hp':self.hp,'stat':self.status,
#             'species':self.species,
#             'element':self.element,
#             'lvl':self.level,
#             'seed':self.seed,
#             'EntityType':self.EntityType,
#             'dc': {
#                 'chars':self.chars, 'colors':self.colors
#             }
#         }
