# Overview

This is the HW1 programming part. I revised the original r-tree, implement the skyline algorithm, and write a new visualization program that produces a png of a file.

## 1. Project Structure

```text
skyline/
├── Dataset_for_PA1                 # Assignment dataset
├── skyline.py                      # Executable CLI
├── skyline_io.py                   # Shared input and verification
├── dynamic_skyline.py              # Incremental skyline maintenance
├── demo_skyline_delete.py          # Delete, plot, and restore demonstration
├── visualize_skyline.py             # Scatter plot and skyline connection
├── requirements-visualization.txt   # Optional plotting dependency
├── pyrtree/
│   ├── __init__.py
│   ├── rtree.py                     # R-tree storage and BBS
│   ├── rect.py                      # Rectangle geometry
│   ├── skyline_region.py            # Exclusive dominance region
│   ├── tests/
│   │   ├── test_rtree.py
│   │   ├── testutil.py
│   │   └── __init__.py
│   └── bench/                      # Original benchmark scripts
├── results/
│   ├── skyline.csv                 # Skyline records
│   └── skyline.png                 # Visualization
├── doc/ref/                        # Original R-tree reference
├── bin/                            # Original benchmark helpers
├── setup.py                        # Original package setup
├── .gitignore
└── README.md
```

## 2. New and Modified Program Files

| File | Status | Purpose |
|---|---|---|
| [pyrtree/rtree.py](pyrtree/rtree.py) | Modified | Fixes Python 3 and point-storage issues and implements `RTree.skyline()` with heap traversal, dominance pruning, native deletion, constrained BBS, and query statistics. |
| [skyline.py](skyline.py) | New | Provides the executable pipeline for parsing arguments, building the R-tree, computing and optionally verifying the skyline, and exporting CSV results. |
| [skyline_io.py](skyline_io.py) | New | Defines point records with original line IDs, validates dataset input, and provides an independent sorting-based skyline reference. |
| [visualize_skyline.py](visualize_skyline.py) | New | Plots all samples and the verified BBS skyline, highlighting and connecting distinct skyline locations in increasing x order. |
| [dynamic_skyline.py](dynamic_skyline.py) | New | Maintains skyline records incrementally on insertion and repairs deletions through exclusive-region BBS. |
| [demo_skyline_delete.py](demo_skyline_delete.py) | New | Computes the assignment skyline, deletes a fixed skyline record, exports a before/after plot, and restores the record with verification. |
| [pyrtree/skyline_region.py](pyrtree/skyline_region.py) | New | Represents the deleted point's exclusive dominance region and provides membership and subtree intersection checks. |


## 3. How to Start

Run commands from the repository root using Python 3; the implementation has been tested with Python 3.13.

### Compute the Skyline


```bash
python3 skyline.py Dataset_for_PA1 --output results/skyline.csv --verify
```

The executable form is equivalent:

```bash
./skyline.py Dataset_for_PA1 --output results/skyline.csv --verify
```

| Argument | Default | Description |
|---|---|---|
| `dataset` | Required | Path to a UTF-8 text file containing two finite numbers per nonblank line. |
| `--output PATH` | `results/skyline.csv` | Destination CSV file; missing parent directories are created. |
| `--seed INTEGER` | `42` | Random seed used by R-tree clustering for reproducible construction. |
| `--verify` | Disabled | Compares BBS record IDs with an independent sorted scan before writing the output. |

Input has no header, with coordinates separated by whitespace:

```text
38.90 23.90
39.75 25.25
38.50 22.25
```

Blank lines are skipped; malformed rows and non-finite coordinates produce an error with the offending line number.

Exit codes are `0` for success, `1` for input/output or verification failure, and `2` for invalid command-line arguments.

### Generate the Visualization

Install the optional plotting dependency in a local virtual environment:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-visualization.txt
.venv/bin/python visualize_skyline.py Dataset_for_PA1 --output results/skyline.png
```

| Argument | Default | Description |
|---|---|---|
| `dataset` | `Dataset_for_PA1` | Input dataset path; unlike the computation CLI, this positional argument is optional. |
| `--output PATH` | `results/skyline.png` | Figure destination; use a `.pdf` extension to export PDF. |
| `--seed INTEGER` | `42` | Random seed used for R-tree construction. |

The plot always checks BBS against the independent reference before saving, prints numbered skyline coordinates, and rejects empty input because there are no samples to display.

## 4. Outcome

For `Dataset_for_PA1`, the program processed **38,377 records** representing **27,543 distinct coordinates** and returned **8 skyline records**, all at distinct coordinates; their record IDs matched the independent sorted-scan result exactly.

### Skyline Data

The following records are saved in [results/skyline.csv](results/skyline.csv); plot labels follow this table's row order.

| Plot label | Record ID (file line) | x | y |
|---|---:|---:|---:|
| 1 | 37348 | 33.82 | 25.82 |
| 2 | 36517 | 33.92 | 20.08 |
| 3 | 37192 | 34.36 | 19.77 |
| 4 | 36286 | 34.78 | 19.24 |
| 5 | 20959 | 35.32 | 19.20 |
| 6 | 33874 | 36.13 | 19.05 |
| 7 | 475 | 36.60 | 19.00 |
| 8 | 37297 | 41.47 | 18.52 |

With seed `42`, BBS expanded **41 internal nodes**, including the root, and pruned **82 entries before heap insertion** and **32 entries after heap removal**; these are in-memory traversal counts, not measured disk I/O.

### Visualization

![All dataset samples with the eight BBS skyline points highlighted and connected](results/skyline.png)

Gray-blue markers show all input samples, while red markers identify skyline locations and labels correspond to the table above; the red segments connect locations in increasing x order as visual guides, not additional data points or a dominance-region boundary.

The R-tree is adapted from [pyrtree](https://code.google.com/archive/p/pyrtree/).


## 5. Extra Credit

The `DynamicSkyline` API supports insertions, deletions, and skyline requests
without rebuilding the R-tree after updates:

```python
from dynamic_skyline import DynamicSkyline
from skyline_io import PointRecord

# IDs identify records, including records with duplicate coordinates.
db = DynamicSkyline([
    PointRecord(1, 2, 2),
    PointRecord(2, 1, 5),
    PointRecord(3, 3, 3),
    PointRecord(4, 4, 2),
    PointRecord(5, 3, 6),
])
print([r.record_id for r in db.skyline()])  # [2, 1]
db.delete(1)
print([r.record_id for r in db.skyline()])  # [2, 3, 4]
print(db.last_update_stats)
db.insert(6, 0, 0)
print([r.record_id for r in db.skyline()])  # [6]
db.delete(6)
print([r.record_id for r in db.skyline()])  # [2, 3, 4]
```

To initialize from the assignment dataset, use
`DynamicSkyline(read_records('Dataset_for_PA1'))` after importing `read_records`
from `skyline_io`.

| Method | Behavior |
|---|---|
| `insert(record_id, x, y)` | Inserts a finite 2-D point, updates the cached skyline by dominance comparisons, and returns the current skyline. |
| `delete(record_id)` | Removes exactly that record, repairs the skyline if necessary, and returns the current skyline. |
| `skyline()` | Returns current records sorted by `(x, y, record_id)` without a new tree search. |
| `records` | Exposes a read-only mapping of active IDs to immutable records. |
| `last_update_stats` | Reports the last update and, for skyline deletion, constrained-query counters. |


### Deletion Demo

With the visualization dependencies installed, run:

```bash
.venv/bin/python demo_skyline_delete.py
```

This will run a skyline to the dataset prof gave to us, then delete one of the skyline points (which will change the skyline), plot the two situations, and add the point back. See skyline_delete_demo.png for details.