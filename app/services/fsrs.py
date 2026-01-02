import math
from datetime import datetime, timedelta
from typing import Tuple, Optional

class FSRS:
    def __init__(self):
        # Default FSRS v4 weights
        self.w = [
            0.4, 0.6, 2.4, 5.8, 4.93, 0.94, 0.86, 0.01, 1.49, 0.14, 0.94, 2.18,
            0.05, 0.34, 1.26, 0.29, 2.61
        ]
        self.p = 0.9  # Request retrievability (default 90%)

    def init_card(self, rating: int) -> Tuple[float, float, float]:
        """
        Initialize a new card.
        Rating: 1 (Again), 2 (Hard), 3 (Good), 4 (Easy)
        Returns: (stability, difficulty, next_interval)
        """
        s = self.w[rating - 1]
        d = self.w[4] - (rating - 3) * self.w[5]
        d = max(1, min(10, d))
        return s, d, s

    def next_interval(self, stability: float) -> int:
        """Calculate next interval in days."""
        return max(1, round(stability))

    def step(self, stability: float, difficulty: float, rating: int, days_since_last_review: float) -> Tuple[float, float, float]:
        """
        Update stability and difficulty based on review.
        Returns: (new_stability, new_difficulty, next_interval)
        """
        retrievability = math.pow(0.9, days_since_last_review / stability)
        
        if rating > 1:  # Correct
            new_s = stability * (
                1 + math.exp(self.w[8]) * (11 - difficulty) * 
                math.pow(stability, -self.w[9]) * 
                (math.exp(self.w[10] * (1 - retrievability)) - 1)
            )
        else:  # Incorrect
            new_s = self.w[11] * math.pow(difficulty, -self.w[12]) * \
                    (math.pow(stability + 1, self.w[13]) - 1) * \
                    math.exp(self.w[14] * (1 - retrievability))
        
        new_d = difficulty - self.w[6] * (rating - 3)
        new_d = max(1, min(10, new_d))
        
        # Clamp stability
        new_s = max(0.1, min(36500, new_s))
        
        return new_s, new_d, new_s
