"""Shared input records and independent reference computation."""
from collections import defaultdict
from dataclasses import dataclass
import math
from pathlib import Path


@dataclass(frozen=True)
class PointRecord:
    record_id: int  # Original, one-based file line number.
    x: float
    y: float


def read_records(path):
    path = Path(path)
    records = []
    with path.open(encoding='utf-8') as source:
        for line_number, line in enumerate(source, 1):
            if not line.strip():
                continue
            try:
                values = tuple(map(float, line.split()))
            except ValueError as exc:
                raise ValueError(f'{path}:{line_number}: expected two finite numbers') from exc
            if len(values) != 2 or not all(map(math.isfinite, values)):
                raise ValueError(f'{path}:{line_number}: expected two finite numbers')
            records.append(PointRecord(line_number, *values))
    return records


def reference_ids(records):
    """Independent 2-D sorted scan, preserving duplicate records."""
    groups = defaultdict(list)
    for record in records:
        groups[(record.x, record.y)].append(record.record_id)
    best_y = math.inf
    result = []
    for (_, y), ids in sorted(groups.items()):
        if y < best_y:
            result.extend(ids)
            best_y = y
    return sorted(result)
