from functools import lru_cache

import numpy as np

MAX_FEATURE_CANDIDATES = 10


@lru_cache(maxsize=32)
def geometric_score(
    rank: int | None,
    p: float = 0.4,
    max_results: int = MAX_FEATURE_CANDIDATES,
) -> float:
    exponent = rank if rank is not None else max_results
    return float(np.log(((1 - p) ** exponent) * p))
