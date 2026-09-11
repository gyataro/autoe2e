from functools import lru_cache

import numpy as np


@lru_cache(maxsize=32)
def geometric_score(rank: int | None, p: float = 0.4, max_rank: int = 4) -> float:
    if rank is not None:
        return float(np.log(((1 - p) ** rank) * p))
    return float(np.log(((1 - p) ** max_rank) * p * p))
