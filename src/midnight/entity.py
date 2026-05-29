from typing import Tuple, Literal, Optional
from .storage import BinStore, BitStore
import numpy as np
import random
import re

GAME_ELEMENTALS = [
    'FIRE',     # 0
    'STAR',     # 1
    'WATER',    # 2
    'GROUND',   # 3
    'WIND',     # 4
    'COSMIC',   # 5
    'NIL'       # 6
]


max_float32 = np.finfo(np.float32).max
def random_float32():
    value = random.random() * max_float32
    return value

class DynamicChar:

    def __init__(
            self,
            colors: list[int] = [17,18,19,20,21,63,105,111,147],
            chars: list[str] = ["@"],
            # How many times per second should 
            # it transition color to color
            color_frequency: float = float(1/16), 
            char_frequency: float = float(1/8), 
        ):

        self.col_freq = color_frequency
        self.chr_freq = char_frequency
        self.chars:list[str] = chars
        self.colors:list[int] = colors + colors[:-1].reverse()

    def color(self, dt:float):
        c=self.colors[int(dt % self.col_freq) % len(self.colors)]
        t=f"\033[38;5;${c}m"
        # t=f"\e[38;5;${c}m"
        return t
    
    def char(self, dt:float, additional_chars:Optional[list[str]]=None):
        if additional_chars is not None:
            _c=self.chars+additional_chars
            return _c[int(dt % self.col_freq) % len(self.colors)]
        return self.chars[int(dt % self.col_freq) % len(self.colors)]

    

class PlayableNonPlayable(DynamicChar):
    def __init__(
            self, 
            yx:Tuple[int, int],
            name:str = 'friend',
            script:Optional[str] = None,
            hp: int = 1,
            status: int = 1,
            species:int = 1,
            element: int = 1,
            level:int = 1,
            seed: Optional[float] = None,
            EntityType:Literal['enemy', 'friend', 'player', 'party'] = 'friend',
            colors: list[int] = [17,18,19,20,21,63,105,111,147],
            chars: list[str] = ["@"],
            color_frequency: float = float(1/16), 
            char_frequency: float = float(1/8), 
        ):
        super().__init__(colors, chars, color_frequency, char_frequency)
        self.yx         = yx          # row, col position
        self.name       = name
        self.script     = script      # For NPC talk
        self.hp         = hp
        self.status     = status      # State/Status such as stunned
        self.species    = species     # in-game species number, affects rendering
        self.element    = element     # Entity Elemental Element
        self.level      = level       # Entity Level
        self.seed       = seed or random_float32()
        self.EntityType = EntityType  # Entity Type, affects update cycles

        pass

    def set_seed(self): random.seed(self.seed)
    def rel_seed(self): random.seed()


class Player(PlayableNonPlayable):

    data_low   = BinStore('player_low', np.uint16, 6)     # 0 to 65535
    data_high  = BinStore('player_high', np.float32, 3)
    data_items = BinStore('player_items', np.uint8, 200)  # 0 to 255
    # data_seen  = BitStore('seen', [(i,1) for i in ])

    def _loadstore(self, store:Literal['low', 'high', 'items']):
        if store=='low':
            return {
                identifier: num
                for identifier,num in Player.data_low.chunked(
                    [
                        'species',
                        'level',
                        'current_hp',
                        'status',
                        'element',
                        'exp'
                    ]
                )
            }
        
        elif store=='high':
            return {
                identifier: num
                for identifier,num in Player.data_high.chunked(
                    [
                        'gametime',
                        'last_game',
                        'seed'
                    ]
                )
            }
        
        elif store=='items':
            return list(Player.data_items.values_until_zero())
        
    def savestore(self):
        ds=self.ds
        Player.data_low.write(
            Player.data_low.formatted(
                [
                    self.species, 
                    self.level, 
                    self.hp, 
                    self.status,
                    self.element,
                    ds[0]['exp']
                ]
            )
        )
        Player.data_high.write(
            Player.data_high.formatted(
                [
                    ds[1]['gametime'],
                    ds[1]['last_game'],
                    self.seed
                ]
            )
        )
        Player.data_items.write(
            Player.data_items.formatted(
                ds[2]
            )
        )
        
    def loadstore(self):
        ds=[ self._loadstore(d) for d in ['low', 'high', 'items'] ]

        # first-run conditions
        if ds[0]['species'] == 0: ds[0]['species'] = 1
        if ds[0]['level'] == 0: ds[0]['level'] = 3
        if ds[0]['current_hp'] == 0: ds[0]['current_hp'] = 25
        if ds[0]['status'] == 0: ds[0]['status'] = 1
        if ds[0]['element'] == 0: ds[0]['element'] = random.randint(1, len(GAME_ELEMENTALS))
        
        if int(ds[1]['seed']) == 0: ds[1]['seed'] = random_float32()

        return ds

    def __init__(self, yx:Tuple[int, int]):

        self.ds = self.loadstore()  # load player data
        
        super().__init__(
            yx=yx, 
            name='midnight', 
            hp=self.ds[0]['current_hp'],
            status=self.ds[0]['status'],
            species=self.ds[0]['species'],
            element=self.ds[0]['element'],
            level=self.ds[0]['level'], 
            seed=self.ds[1]['seed'],
            EntityType='player',
            chars=["𓃥", "@"]
        )

        pass

