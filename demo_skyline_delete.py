#!/usr/bin/env python3
"""Demonstrate exclusive-region skyline deletion, plot it, then restore the point."""
import os
from pathlib import Path
import random

from dynamic_skyline import DynamicSkyline
from skyline_io import read_records, reference_ids

ROOT = Path(__file__).resolve().parent
DATASET = ROOT / 'Dataset_for_PA1'
DELETE_ID = 37348  # Original line number: (33.82, 25.82).
OUTPUT = ROOT / 'results' / 'skyline_delete_demo.png'


def verify(db):
    if sorted(r.record_id for r in db.skyline()) != reference_ids(db.records.values()):
        raise RuntimeError('Dynamic skyline disagrees with the independent reference')


def draw_panel(ax, records, skyline, title, limits, changed_ids):
    ax.scatter([r.x for r in records], [r.y for r in records], s=5,
               color='#71869b', alpha=0.25, linewidths=0, rasterized=True,
               label=f'Samples ({len(records):,})')
    frontier = sorted({(r.x, r.y) for r in skyline})
    xs, ys = zip(*frontier)
    ax.plot(xs, ys, color='#df4b35', linewidth=1.5, zorder=3)
    ax.scatter(xs, ys, s=42, color='#df4b35', edgecolors='white', linewidths=0.7,
               zorder=4, label=f'Skyline ({len(skyline)} records)')
    changed = [r for r in skyline if r.record_id in changed_ids]
    if changed:
        ax.scatter([r.x for r in changed], [r.y for r in changed], s=125,
                   facecolors='none', edgecolors='#16736c', linewidths=1.5,
                   zorder=5, label='Changed skyline locations')
        for r in changed:
            ax.annotate(f'ID {r.record_id}', (r.x, r.y), xytext=(8, 10),
                        textcoords='offset points', fontsize=8, color='#125c56')
    ax.set_title(title, loc='left', fontsize=12)
    ax.set_xlabel('x (smaller is better)')
    ax.set_ylabel('y (smaller is better)')
    ax.set_xlim(*limits[0])
    ax.set_ylim(*limits[1])
    ax.grid(alpha=0.15)
    ax.set_axisbelow(True)
    ax.spines[['top', 'right']].set_visible(False)
    ax.legend(loc='upper right', fontsize=8)


def main():
    os.environ.setdefault('MPLCONFIGDIR', str(ROOT / '.matplotlib'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    random.seed(42)
    original = read_records(DATASET)
    db = DynamicSkyline(original)
    verify(db)
    before = db.skyline()
    before_ids = {r.record_id for r in before}
    if DELETE_ID not in before_ids:
        raise RuntimeError(f'Expected record {DELETE_ID} to be a skyline point')
    removed = db.records[DELETE_ID]
    print(f'Before: {len(db.records):,} records; {len(before)} skyline records.')
    print(f'Deleting ID {DELETE_ID}: ({removed.x}, {removed.y})')

    try:
        db.delete(DELETE_ID)
        verify(db)
        after = db.skyline()
        new_ids = {r.record_id for r in after} - before_ids
        print(f'After: {len(db.records):,} records; {len(after)} skyline records.')
        print(f'New skyline IDs: {sorted(new_ids)}')
        print(f'Exclusive-region nodes expanded: {db.last_update_stats["expanded_nodes"]}')

        limits = []
        for values in ([r.x for r in original], [r.y for r in original]):
            low, high = min(values), max(values)
            margin = max((high - low) * 0.06, 0.1)
            limits.append((low - margin, high + margin))
        fig, axes = plt.subplots(1, 2, figsize=(15, 7.5), layout='constrained')
        try:
            draw_panel(axes[0], original, before, 'Before deletion', limits, {DELETE_ID})
            draw_panel(axes[1], list(db.records.values()), after,
                       f'After deleting ID {DELETE_ID}', limits, new_ids)
            fig.suptitle('Dynamic Skyline — Dataset_for_PA1', fontsize=16)
            fig.supxlabel('Both results independently verified. Lines connect skyline locations only.\n'
                          'The deleted record is restored in memory after exporting this snapshot.',
                          fontsize=10, color='#526071')
            OUTPUT.parent.mkdir(parents=True, exist_ok=True)
            fig.savefig(OUTPUT, dpi=180)
        finally:
            plt.close(fig)
    finally:
        # Restore even if verification or plotting fails after the deletion.
        if DELETE_ID not in db.records:
            db.insert(removed.record_id, removed.x, removed.y)
        verify(db)
        if dict(db.records) != {r.record_id: r for r in original}:
            raise RuntimeError('Original records were not fully restored')
        if {r.record_id for r in db.skyline()} != before_ids:
            raise RuntimeError('Original skyline was not restored')
        print(f'Restored ID {DELETE_ID}; original records and skyline verified.')
    print(f'Saved: {OUTPUT}')


if __name__ == '__main__':
    main()
