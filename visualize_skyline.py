#!/usr/bin/env python3
"""Plot all samples and the BBS skyline, checked against a sorted scan."""
import argparse
import os
from pathlib import Path
import random

from pyrtree import Rect, RTree


from skyline_io import read_records, reference_ids


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dataset', nargs='?', type=Path, default=Path('Dataset_for_PA1'))
    parser.add_argument('--output', type=Path, default=Path('results/skyline.png'))
    parser.add_argument('--seed', type=int, default=42, help='R-tree clustering seed (default: 42)')
    args = parser.parse_args()
    try:
        records = read_records(args.dataset)
        if not records:
            raise ValueError(f'{args.dataset}: no points to plot')
        points = [(r.x, r.y) for r in records]
    except (OSError, ValueError) as exc:
        parser.error(str(exc))

    random.seed(args.seed)
    tree = RTree()
    for record in records:
        tree.insert(record, Rect(record.x, record.y, record.x, record.y))
    skyline_records = tree.skyline()
    skyline_ids = [r.record_id for r in skyline_records]
    expected = reference_ids(records)
    if sorted(skyline_ids) != expected:
        raise RuntimeError('BBS disagrees with the independent sorted scan; plot not generated')

    os.environ.setdefault('MPLCONFIGDIR', str(Path(__file__).resolve().parent / '.matplotlib'))
    import matplotlib
    matplotlib.use('Agg')  # Save an artifact without requiring a GUI.
    import matplotlib.pyplot as plt

    # Deduplicate only the visual markers; BBS results retain all record IDs.
    frontier = sorted({(r.x, r.y) for r in skyline_records})
    fig, ax = plt.subplots(figsize=(10, 8), layout='constrained')
    fig.set_facecolor('#fafbfc')
    ax.set_facecolor('white')
    xs, ys = zip(*points)
    ax.scatter(xs, ys, s=7, c='#71869b', alpha=0.28, linewidths=0,
               rasterized=True, label=f'All samples ({len(points):,} records)', zorder=2)
    sx, sy = zip(*frontier)
    ax.plot(sx, sy, color='#df4b35', linewidth=1.6, zorder=3,
            label='Skyline connection (sorted by x)')
    ax.scatter(sx, sy, s=76, c='#df4b35', edgecolors='white', linewidths=1.2,
               zorder=4, label=f'BBS skyline ({len(skyline_ids)} records / {len(frontier)} locations)')
    for i, (x, y) in enumerate(frontier, 1):
        ax.annotate(str(i), (x, y), xytext=(7, -12), textcoords='offset points',
                    fontsize=9, color='#a32b1b', weight='bold', zorder=5)
    ax.set_title('Skyline of ' + args.dataset.name + '\n'
                 'Minimize both dimensions · BBS verified against independent sorted scan',
                 loc='left', fontsize=13, pad=16)
    ax.set_xlabel('x (smaller is better)')
    ax.set_ylabel('y (smaller is better)')
    ax.grid(alpha=0.16, zorder=0)
    ax.set_axisbelow(True)
    ax.margins(0.07)
    ax.spines[['top', 'right']].set_visible(False)
    ax.legend(loc='upper right', fontsize=9, framealpha=0.95)
    fig.supxlabel('Connected segments are visual guides, not additional data points.',
                  fontsize=9, color='#526071')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output, dpi=180)
    plt.close(fig)
    print(f'Verified: {len(points):,} records; {len(skyline_ids)} skyline records; '
          f'{len(frontier)} skyline locations.')
    print('Skyline coordinates (plot labels):')
    for i, (x, y) in enumerate(frontier, 1):
        print(f'  {i}: ({x:g}, {y:g})')
    print(f'Saved: {args.output.resolve()}')


if __name__ == '__main__':
    main()
