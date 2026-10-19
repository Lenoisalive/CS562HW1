"""Incremental insertion and exclusive-region deletion for 2-D skylines."""
import math
from types import MappingProxyType

from pyrtree import Rect, RTree
from pyrtree.skyline_region import dominates
from skyline_io import PointRecord


class DynamicSkyline:
    def __init__(self, records=()):
        self.tree = RTree()
        self._records = {}
        self._skyline = {}
        self.last_update_stats = {}
        for record in records:
            self._validate(record.record_id, record.x, record.y)
            self._records[record.record_id] = record
            self.tree.insert(record, Rect(record.x, record.y, record.x, record.y))
        self._skyline = {r.record_id: r for r in self.tree.skyline()}

    @property
    def records(self):
        return MappingProxyType(self._records)

    def _validate(self, record_id, x, y):
        if not isinstance(record_id, int) or isinstance(record_id, bool):
            raise ValueError('record_id must be an integer')
        if record_id in self._records:
            raise ValueError(f'Duplicate record ID: {record_id}')
        if not math.isfinite(x) or not math.isfinite(y):
            raise ValueError('Coordinates must be finite')

    def skyline(self):
        """Return a fresh list of current immutable records, without tree search."""
        return sorted(self._skyline.values(), key=lambda r: (r.x, r.y, r.record_id))

    def insert(self, record_id, x, y):
        self._validate(record_id, x, y)
        record = PointRecord(record_id, x, y)
        self.tree.insert(record, Rect(x, y, x, y))
        self._records[record_id] = record
        removed = []
        if not any(dominates((s.x, s.y), (x, y)) for s in self._skyline.values()):
            removed = [s.record_id for s in self._skyline.values()
                       if dominates((x, y), (s.x, s.y))]
            for key in removed:
                del self._skyline[key]
            self._skyline[record_id] = record
        self.last_update_stats = dict(operation='insert', constrained_bbs=False,
                                      removed_skyline_ids=removed)
        return self.skyline()

    def delete(self, record_id):
        """Delete by ID; recompute only D(p) minus remaining skyline dominance."""
        record = self._records[record_id]  # Missing IDs raise KeyError without mutation.
        if not self.tree.delete(record, Rect(record.x, record.y, record.x, record.y)):
            raise RuntimeError('Record is missing from the R-tree')
        del self._records[record_id]
        self.last_update_stats = dict(operation='delete', constrained_bbs=False,
                                      added_skyline_ids=[])
        if record_id not in self._skyline:
            return self.skyline()
        del self._skyline[record_id]
        remaining = [(s.x, s.y) for s in self._skyline.values()]
        new_records = self.tree.constrained_skyline((record.x, record.y), remaining)
        self._skyline.update((r.record_id, r) for r in new_records)
        self.last_update_stats.update(constrained_bbs=True,
                                      added_skyline_ids=[r.record_id for r in new_records],
                                      **self.tree.skyline_stats)
        return self.skyline()
