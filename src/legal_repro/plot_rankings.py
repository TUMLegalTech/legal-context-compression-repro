#!/usr/bin/env python3
"""CPU-only ranking-figure draft: retain below/tied/above proportions, not a leaderboard."""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path

from .figure_style import ANNOTATION_SIZE, AXIS_COLOR, AXIS_LABEL_SIZE, FIGURE_WIDTH, FONT_FAMILY, FORMATS, INK, PALETTE, save_plot, styled
from .plot_score_dimensions import MANIFEST_SHA, METHODS, RATIOS, REPO, SOURCE, sha


RELATIONS = {
    'below': ('Ranked below uncompressed', PALETTE['purple'], 'white'),
    'tied': ('Tied', PALETTE['blue'], 'white'),
    'above': ('Ranked above uncompressed', PALETTE['green'], INK),
}


def load_rankings() -> tuple[list[dict], str]:
    manifest_bytes = (SOURCE / 'MANIFEST.json').read_bytes()
    if hashlib.sha256(manifest_bytes).hexdigest() != MANIFEST_SHA:
        raise ValueError('The verified paper manifest changed')
    manifest = json.loads(manifest_bytes)
    relative = 'evidence/ranking_summary.json'
    content = (SOURCE / relative).read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    if digest != manifest['files_sha256'][relative]:
        raise ValueError('The accepted ranking summary changed')
    summary = json.loads(content)
    if (summary['status'] != 'FULL_526_RANKING_COMPLETE' or summary['rows'] != 526
            or summary['primary_ranks'] != 7890 or summary['retests'] != 789
            or summary['global_fifteen_method_order_established'] is not False):
        raise ValueError('Unexpected ranking scope')
    expected = {f'{method}-{suffix}' for method in METHODS for suffix in RATIOS}
    blocks = [('rank_summary', 526), ('original_128_rank_summary', 128),
              ('additional_398_rank_summary', 398)]
    for block, count in blocks:
        if set(summary[block]) != expected:
            raise ValueError('Incomplete ranking condition coverage')
        for values in summary[block].values():
            if values['rows'] != count:
                raise ValueError('Unexpected question coverage')
            for control in ('raw', 'no_context', 'oracle_bgb_paragraph_ids'):
                counts = [values[f'compressed_{relation}_{control}'] for relation in RELATIONS]
                if any(type(value) is not int or value < 0 for value in counts) or sum(counts) != count:
                    raise ValueError('Invalid ranking counts')
    for candidate, values in summary['rank_summary'].items():
        for key, value in values.items():
            if value != sum(summary[block][candidate][key] for block, _ in blocks[1:]):
                raise ValueError('Original and additional blocks do not reproduce combined counts')
    rows = []
    for method in METHODS:
        for suffix, (ratio, _marker) in RATIOS.items():
            identifier = f'{method}-{suffix}'
            values = summary['rank_summary'][identifier]
            row = {'candidate_id': identifier, 'method': method, 'requested_ratio': ratio,
                   'questions': values['rows']}
            for relation in RELATIONS:
                row[f'{relation}_count'] = values[f'compressed_{relation}_raw']
                row[f'{relation}_percent'] = 100 * row[f'{relation}_count'] / row['questions']
            rows.append(row)
    return rows, digest


@styled
def draw(rows: list[dict], output: Path) -> None:
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch

    fig = plt.figure(figsize=(FIGURE_WIDTH, 4.8), facecolor='white')
    labels = []
    for column, (ratio, _marker) in enumerate(RATIOS.values()):
        ax = fig.add_axes([0.215 + column * 0.255, 0.20, 0.225, 0.59])
        ax.set(xlim=(0, 100), ylim=(4.65, -0.65), xticks=[0, 50, 100], yticks=range(5))
        ax.set_yticklabels([label for label, _ in METHODS.values()] if column == 0 else [''] * 5)
        ax.tick_params(axis='y', length=0, pad=12)
        ax.tick_params(axis='x', length=3, color=AXIS_COLOR)
        ax.spines[['top', 'right', 'left']].set_visible(False)
        ax.spines['bottom'].set_color(AXIS_COLOR)
        labels.append(ax.set_title(f'{ratio:.2f}× requested target', pad=13))
        labels.extend(ax.get_yticklabels())
        labels.extend(ax.get_xticklabels())
        for index, method in enumerate(METHODS):
            matches = [row for row in rows if row['method'] == method and row['requested_ratio'] == ratio]
            if len(matches) != 1:
                raise ValueError('Expected exactly one bar per method and target')
            row, left = matches[0], 0.0
            for relation, (_label, color, text_color) in RELATIONS.items():
                width = row[f'{relation}_percent']
                rectangle, = ax.barh(index, width, left=left, height=0.62,
                                     color=color, edgecolor='white', linewidth=0.7)
                if (not math.isclose(rectangle.get_x(), left, rel_tol=0, abs_tol=1e-12)
                        or not math.isclose(rectangle.get_width(), width, rel_tol=0, abs_tol=1e-12)):
                    raise ValueError('Rendered segment differs from accepted proportions')
                labels.append(ax.text(left + width / 2, index, f'{width:.1f}',
                                      ha='center', va='center', fontsize=ANNOTATION_SIZE, color=text_color))
                left += width
            if not math.isclose(left, 100, abs_tol=1e-12):
                raise ValueError('A ranking bar does not sum to 100 percent')
    handles = [Patch(facecolor=color, label=label) for label, color, _ in RELATIONS.values()]
    labels.append(fig.legend(handles=handles, loc='center', bbox_to_anchor=(0.5825, 0.945),
                             ncol=3, frameon=False, handlelength=1.35))
    labels.append(fig.text(0.5825, 0.060, 'Share of questions (%)', ha='center', fontsize=AXIS_LABEL_SIZE))
    save_plot(fig, output, 'ranking_comparisons', labels)
    plt.close(fig)





