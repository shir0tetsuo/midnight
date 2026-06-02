from .buffer import TerminalBuffer
from .ansicodes import *
import numpy as np

class OverheadCamera(TerminalBuffer):

    def __init__(
            self,
            world_position: tuple[int,int],
            seed: np.float32,
            world_map: np.ndarray
        ):
        super().__init__()
        self.Wy, self.Wx = world_position
        self.seed = seed
        self.world_map = world_map

    def update(
            self, 
            Wy:int,Wx:int, # world y and world x
            y_rows:int,  # global terminal rows
            x_cols:int,  # global terminal cols
            world_objects_calc,
            offset:tuple[int,int]=(0,0) # rows, cols offset
        ):
        self.primary = []  # Reset the object buffer
        for r in range(0,y_rows,1):
            self.primary.append(
                (
                    Cursor(r+offset[0],offset[1]),
                    
                )
            )
            
