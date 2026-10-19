"""Implicit exclusive dominance region for minimum skyline deletion."""
import math


def dominates(a, b):
    return a[0] <= b[0] and a[1] <= b[1] and (a[0] < b[0] or a[1] < b[1])


class ExclusiveDominanceRegion:
    """D(deleted) minus the union of D(s) for remaining skyline points.

    Membership is exact. MBR intersection is conservative: false always means
    no eligible point, while true may include a boundary-only false positive.
    No enumeration of database points or geometric epsilon is needed.
    """
    def __init__(self, deleted, remaining):
        self.deleted = tuple(deleted)
        self.remaining = tuple(tuple(p) for p in remaining)
        for p in (self.deleted,) + self.remaining:
            if len(p) != 2 or not all(math.isfinite(v) for v in p):
                raise ValueError('Region requires finite 2-D coordinates')
        # In particular, an equal-coordinate survivor covers all of D(deleted).
        self.empty = any(s[0] <= self.deleted[0] and s[1] <= self.deleted[1]
                         for s in self.remaining)

    def lower_bound(self, rect):
        return max(rect.x, self.deleted[0]), max(rect.y, self.deleted[1])

    def contains(self, x, y):
        p = (x, y)
        return (not self.empty and dominates(self.deleted, p)
                and not any(dominates(s, p) for s in self.remaining))

    def intersects(self, rect):
        if self.empty:
            return False
        low = self.lower_bound(rect)
        if low[0] > rect.xx or low[1] > rect.yy:
            return False
        if not dominates(self.deleted, (rect.xx, rect.yy)):
            return False
        # Every point in this clipped MBR is at least its lower corner.
        return not any(dominates(s, low) for s in self.remaining)
