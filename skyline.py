#!/usr/bin/env python3
"""Load 2-D points, build an R-tree, compute BBS skyline, and write CSV."""
import argparse
import csv
import os
from pathlib import Path
import random
import sys
import tempfile
import time

from pyrtree import Rect, RTree
from skyline_io import read_records, reference_ids


def check_output_path(dataset, output):
    if (dataset.resolve() == output.resolve()
            or (output.exists() and dataset.samefile(output))):
        raise ValueError('output must not overwrite the input dataset')


def write_csv(path, records):
    """Replace output only after a complete CSV has been written."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', newline='',
                                         dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            writer = csv.writer(stream)
            writer.writerow(['record_id', 'x', 'y'])
            for record in sorted(records, key=lambda r: (r.x, r.y, r.record_id)):
                writer.writerow([record.record_id, record.x, record.y])
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, add_help=False)
    parser.add_argument('dataset', type=Path, help='two finite numbers per nonblank line')
    parser.add_argument('--output', type=Path, default=Path('results/skyline.csv'))
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--verify', action='store_true', help='check against independent sorted scan')
    args = parser.parse_args(argv)
    try:
        check_output_path(args.dataset, args.output)
        start = time.perf_counter()
        records = read_records(args.dataset)
        read_seconds = time.perf_counter() - start
        random.seed(args.seed)
        start = time.perf_counter()
        tree = RTree()
        for record in records:
            tree.insert(record, Rect(record.x, record.y, record.x, record.y))
        build_seconds = time.perf_counter() - start
        result = tree.skyline()
        verify_seconds = None
        if args.verify:
            start = time.perf_counter()
            if sorted(r.record_id for r in result) != reference_ids(records):
                raise ValueError('BBS verification failed; output was not written')
            verify_seconds = time.perf_counter() - start
        check_output_path(args.dataset, args.output)
        write_csv(args.output, result)
    except (OSError, ValueError) as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 1

    stats = tree.skyline_stats
    print(f'Input records: {len(records):,}')
    print(f'Skyline records: {len(result):,}')
    print(f'Read time: {read_seconds:.6f} s')
    print(f'Build time: {build_seconds:.6f} s')
    print(f'BBS query time: {stats["elapsed_seconds"]:.6f} s')
    print(f'Expanded nodes: {stats["expanded_nodes"]}')
    print(f'Pruned entries (before push / after pop): '
          f'{stats["pruned_before_push"]} / {stats["pruned_after_pop"]}')
    if verify_seconds is not None:
        print(f'Verification: PASS ({verify_seconds:.6f} s; excluded from BBS time)')
    print(f'Output: {args.output.resolve()}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
