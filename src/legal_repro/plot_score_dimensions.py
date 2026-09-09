#!/usr/bin/env python3
"""Three lean, mean-only dimension plots from verified, unchanged paper data.

CPU-only. Write PNG/SVG and companion values to a fresh paper/figures child.
Paired difference intervals remain in the CSV; they are not absolute-score CIs.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
import math
import os
from pathlib import Path

from .figure_style import AXIS_COLOR, FIGURE_WIDTH, FONT_FAMILY, FORMATS, GRID_COLOR, PALETTE, SCORE_FONT_SIZES, SCORE_RC_PARAMS, save_plot, styled

from .paths import ASSETS
REPO = ASSETS
SOURCE = REPO / 'paper'
MANIFEST_SHA = '8cb3810823bbeb165025f8b4f543a89ede08d9c24d37c161a3364618cd658a31'
METHODS = {
    'legal_llmlingua2': ('Legal LLMLingua-2', PALETTE['purple']),
    'xprovence_six_probe_atoms': ('XProvence', PALETTE['blue']),
    'multi_probe_bge': ('Multi-probe BGE', PALETTE['teal']),
    'german_legal_selector_v2': ('German legal selector', PALETTE['green']),
    'dac_native_tokens': ('DAC', PALETTE['yellow']),
}
RATIOS = {'r1p1': (1.1, 'o'), 'r1p25': (1.25, 's'), 'r2p0': (2.0, '^')}
METRICS = {
    'outcome_correctness': 'Outcome correctness',
    'legal_reasoning_correctness': 'Legal reasoning correctness',
    'legal_basis_correctness': 'Legal basis correctness',
}
# Keep every measured method and the two retained references visible. The
# ranges differ deliberately; compare numerical ticks, not apparent slopes.
Y_AXES = {
    'outcome_correctness': (0.545, 0.635, 0.02),
    'legal_reasoning_correctness': (0.400, 0.565, 0.04),
    'legal_basis_correctness': (0.395, 0.635, 0.05),
}
X_LIMITS = (1.0, 2.3)
TARGET_MARKERS = {ratio: marker for ratio, marker in RATIOS.values()}
REFERENCES = {
    'raw': ('Uncompressed statute text', '#536371', (0, (6, 4))),
    'oracle_bgb_paragraph_ids': ('Paragraph IDs', '#7e8a95', (0, (4, 3, 1, 3))),
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_verified_tables() -> tuple[dict, list[dict], dict]:
    """Parse the exact bytes verified against the pinned, unchanged paper manifest."""
    manifest_bytes = (SOURCE / 'MANIFEST.json').read_bytes()
    if hashlib.sha256(manifest_bytes).hexdigest() != MANIFEST_SHA:
        raise ValueError('The verified paper manifest changed')
    manifest = json.loads(manifest_bytes)
    tables, bindings = {}, {}
    for name in ('condition_means.csv', 'all_180_contrasts.csv'):
        relative = 'evidence/' + name
        content = (SOURCE / relative).read_bytes()
        bindings[relative] = hashlib.sha256(content).hexdigest()
        if bindings[relative] != manifest['files_sha256'][relative]:
            raise ValueError(f'Accepted numerical evidence changed: {name}')
        tables[name] = list(csv.DictReader(io.StringIO(content.decode('utf-8'))))
    mean_rows = tables['condition_means.csv']
    means = {row['condition_id']: row for row in mean_rows}
    contrasts = tables['all_180_contrasts.csv']
    expected = {f'{method}-{suffix}' for method in METHODS for suffix in RATIOS}
    if (len(mean_rows) != 18 or set(means) != expected | set(REFERENCES) | {'no_context'}
            or len(contrasts) != 180):
        raise ValueError('Unexpected source coverage')
    return means, contrasts, bindings


def realized_compression_ratio(deletion_percent: float) -> float:
    """Original/retained token totals, not an average of per-question ratios."""
    if not math.isfinite(deletion_percent) or deletion_percent >= 100:
        raise ValueError('A finite compression ratio requires positive retained tokens')
    return 1 / (1 - deletion_percent / 100)


def load_dimensions() -> tuple[list[dict], list[dict], dict]:
    means, contrasts, bindings = load_verified_tables()
    selected = [r for r in contrasts if r['reference'] == 'raw' and r['metric'] in METRICS]
    indexed = {(r['candidate_id'], r['metric']): r for r in selected}
    expected = {(f'{method}-{suffix}', metric)
                for method in METHODS for suffix in RATIOS for metric in METRICS}
    if len(selected) != len(expected) or set(indexed) != expected:
        raise ValueError('Expected 45 unique dimension-versus-uncompressed comparisons')
    positions = []
    for method in METHODS:
        for suffix, (ratio, _marker) in RATIOS.items():
            identifier = f'{method}-{suffix}'
            condition = means[identifier]
            deletion = 100 * float(condition['row_weighted_downstream_deletion_fraction'])
            realized_ratio = realized_compression_ratio(deletion)
            if (float(condition['requested_ratio']) != ratio
                    or not X_LIMITS[0] <= realized_ratio <= X_LIMITS[1]):
                raise ValueError(f'Requested or realized compression ratio changed: {identifier}')
            positions.append({'candidate_id': identifier, 'method': method, 'ratio': ratio,
                              'actual_deletion_percent': deletion,
                              'realized_compression_ratio': realized_ratio})
    points, controls = [], []
    for metric in METRICS:
        ymin, ymax, _tick = Y_AXES[metric]
        baseline = float(means['raw'][metric])
        for control in REFERENCES:
            score = float(means[control][metric])
            if not math.isfinite(score) or not ymin <= score <= ymax:
                raise ValueError('Reference outside the metric-specific score axis')
            controls.append({'metric': metric, 'condition_id': control, 'mean_score': score})
        for position in positions:
            identifier = position['candidate_id']
            score = float(means[identifier][metric])
            contrast = indexed[(identifier, metric)]
            low, high = json.loads(contrast['ci95'])
            difference = float(contrast['mean_difference'])
            if (not math.isfinite(score) or not ymin <= score <= ymax
                    or not all(math.isfinite(value) for value in (low, difference, high))
                    or not low <= difference <= high
                    or int(contrast['rows']) != 526 or int(contrast['clusters']) != 360
                    or contrast['estimand'] != 'evaluation_row_mean_with_context_cluster_resampling'
                    or not math.isclose(score - baseline, difference, abs_tol=1e-12)):
                raise ValueError(f'Dimension score or paired comparison changed: {identifier}/{metric}')
            points.append({'metric': metric, 'candidate_id': identifier,
                           'method': position['method'], 'requested_ratio': position['ratio'],
                           'actual_deletion_percent': position['actual_deletion_percent'],
                           'realized_compression_ratio': position['realized_compression_ratio'],
                           'target_marker': TARGET_MARKERS[position['ratio']],
                           'mean_score': score, 'mean_difference_vs_uncompressed': difference,
                           'paired_difference_ci95_low': low, 'paired_difference_ci95_high': high})
    return points, controls, bindings


@styled(overrides=SCORE_RC_PARAMS)
def draw(metric, points, controls, output):
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    from matplotlib.ticker import MultipleLocator, FormatStrFormatter

    fig = plt.figure(figsize=(FIGURE_WIDTH, 6.4), facecolor='white')
    ax = fig.add_axes([0.125, 0.305, 0.60, 0.63])
    ymin, ymax, tick = Y_AXES[metric]
    ax.set(xlim=X_LIMITS, ylim=(ymin, ymax),
           xlabel='Realized compression ratio (×)', ylabel='Mean Gold-agreement score')
    ax.xaxis.labelpad = 10
    ax.yaxis.labelpad = 10
    ax.xaxis.set_major_locator(MultipleLocator(0.2))
    ax.xaxis.set_major_formatter(FormatStrFormatter('%.1f'))
    ax.yaxis.set_major_locator(MultipleLocator(tick))
    ax.yaxis.set_major_formatter(FormatStrFormatter('%.2f'))
    ax.spines[['top', 'right']].set_visible(False)
    ax.spines[['left', 'bottom']].set_color(AXIS_COLOR)
    ax.tick_params(length=3, width=0.6, color=AXIS_COLOR)
    ax.set_axisbelow(True)
    ax.grid(axis='y', color=GRID_COLOR, linewidth=0.6)
    labels = []
    for control in (c for c in controls if c['metric'] == metric):
        label, color, style = REFERENCES[control['condition_id']]
        score = control['mean_score']
        reference = ax.axhline(score, color=color, linestyle=style, linewidth=1.0, zorder=1)
        if any(float(value) != score for value in reference.get_ydata()):
            raise ValueError('Reference line rendered at the wrong score')
        labels.append(ax.text(1.025, score, label, transform=ax.get_yaxis_transform(),
                              ha='left', va='center', fontsize=SCORE_FONT_SIZES['annotations'], color=color,
                              linespacing=1.45, clip_on=False))
    for method, (_label, color) in METHODS.items():
        rows = [p for p in points if p['metric'] == metric and p['method'] == method]
        if len(rows) != 3:
            raise ValueError('Each method must have all three observed settings')
        line_color = '#b59d08' if method == 'dac_native_tokens' else color
        line, = ax.plot([p['realized_compression_ratio'] for p in rows],
                        [p['mean_score'] for p in rows], color=line_color, linewidth=1.65, zorder=3)
        if (list(line.get_xdata()) != [p['realized_compression_ratio'] for p in rows]
                or list(line.get_ydata()) != [p['mean_score'] for p in rows]):
            raise ValueError('Rendered coordinates differ from the accepted means')
        for point in rows:
            marker, = ax.plot(point['realized_compression_ratio'], point['mean_score'],
                              linestyle='none', marker=point['target_marker'], markersize=6.5,
                              markerfacecolor=color, markeredgecolor='#334450',
                              markeredgewidth=0.55, zorder=4)
            if (marker.get_marker() != TARGET_MARKERS[point['requested_ratio']]
                    or float(marker.get_xdata()[0]) != point['realized_compression_ratio']
                    or float(marker.get_ydata()[0]) != point['mean_score']):
                raise ValueError('Rendered target marker or coordinate is incorrect')
    handles = [Line2D([], [], color='#b59d08' if method == 'dac_native_tokens' else color,
                      linewidth=2.0, label=label)
               for method, (label, color) in METHODS.items()]
    # Matplotlib fills columns: this permutation keeps the original method order
    # when the enlarged legend is read left-to-right across its two rows.
    handles = [handles[index] for index in (0, 3, 1, 4, 2)]
    legend = fig.legend(handles=handles, loc='lower center', bbox_to_anchor=(0.515, 0.026),
                        ncol=3, frameon=False, handlelength=1.7,
                        handletextpad=0.55, columnspacing=1.45)
    target_handles = [Line2D([], [], linestyle='none', marker=marker, markersize=6.3,
                            markerfacecolor='white', markeredgecolor='#526271',
                            markeredgewidth=0.8, label=f'{ratio:.2f}×')
                      for ratio, marker in TARGET_MARKERS.items()]
    target_legend = fig.legend(handles=target_handles, title='Requested target',
                               loc='upper left', bbox_to_anchor=(0.73, 0.47),
                               frameon=False,
                               handlelength=1.2, handletextpad=0.6, labelspacing=0.8)
    save_plot(fig, output, metric, [legend, target_legend, *labels, ax.xaxis.label, ax.yaxis.label])
    plt.close(fig)





