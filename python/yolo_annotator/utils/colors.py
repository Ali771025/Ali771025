from typing import Tuple, List
PALETTE = [
    (255,0,0),(0,255,0),(0,0,255),(255,255,0),(255,0,255),(0,255,255),
    (128,0,128),(255,128,0),(0,128,255),(128,255,0),(255,0,128),(0,255,128),
    (128,128,0),(128,0,0),(0,128,0),(0,0,128)
]
def get_color(idx: int) -> Tuple[int,int,int]:
    return PALETTE[idx % len(PALETTE)]

def generate_colors(n: int) -> List[Tuple[int,int,int]]:
    import random
    random.seed(0)
    colors=[]
    for i in range(n):
        if i < len(PALETTE):
            colors.append(PALETTE[i])
        else:
            colors.append((random.randint(0,255), random.randint(0,255), random.randint(0,255)))
    return colors
