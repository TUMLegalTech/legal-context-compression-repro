#!/usr/bin/env python3
"""Build the four final, consistently styled figures from accepted data; CPU only."""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import sys
import zipfile

from .figure_style import ANNOTATION_SIZE, AXIS_LABEL_SIZE, FONT_FAMILY, FORMATS, LEGEND_SIZE, PALETTE, PANEL_LABEL_SIZE, SCORE_FONT_SIZES, TICK_LABEL_SIZE
from . import plot_score_dimensions as scores
from . import plot_rankings as rankings


REPO = scores.REPO
PLOT_NAMES = (*scores.METRICS, 'ranking_comparisons')
PUBLISHED_FILES = tuple(f'{name}.{extension}' for name in PLOT_NAMES for extension in FORMATS) + (
    'data/score_values.csv', 'data/reference_values.csv', 'data/ranking_values.csv', 'README.md')


def build(output: Path) -> dict:
    absolute = output.expanduser().absolute()
    output = absolute.resolve()
    if absolute != output or output.exists() or output.is_relative_to(scores.REPO):
        raise PermissionError('Use a fresh output directory outside packaged resources')
    points, controls, source_bindings = scores.load_dimensions()
    rank_rows, rank_hash = rankings.load_rankings()
    source_bindings['evidence/ranking_summary.json'] = rank_hash
    output.mkdir(parents=True)
    os.environ['MPLCONFIGDIR'] = str(output / '.matplotlib-cache')
    import matplotlib
    matplotlib.use('Agg')
    from matplotlib.font_manager import FontProperties, findfont

    for metric in scores.METRICS:
        scores.draw(metric, points, controls, output)
    rankings.draw(rank_rows, output)
    data = output / 'data'
    data.mkdir()
    tables = {'score_values.csv': points, 'reference_values.csv': controls, 'ranking_values.csv': rank_rows}
    for name, rows in tables.items():
        with (data / name).open('x', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    (output / 'README.md').write_text(
        '# Final plots\n\n'
        'Use this folder for the four current plots. All use STIXGeneral serif type, '
        'no overall titles, the same 12-inch export width, and a shared '
        'purple-blue-teal-green-yellow palette. Ranking colors are drawn from that '
        'palette: purple = below uncompressed, blue = tied, green = above uncompressed. '
        'Method colors in the score plots retain their previous meanings. '
        'Score-figure axis labels are 19 pt; their legends, tick labels and reference '
        'labels are 17 pt, with a two-row method legend. Ranking typography is unchanged: '
        'the axis label is 15 pt, legends, ticks and percentages are 13 pt, and '
        'requested-target panel labels are 14 pt.\n\n'
        '| Plot | Image | Vector | Paper-ready |\n| --- | --- | --- | --- |\n' +
        ''.join(f'| {title} | [PNG]({name}.png) | [SVG]({name}.svg) | [PDF]({name}.pdf) |\n'
                for name, title in [*scores.METRICS.items(), ('ranking_comparisons', 'Ranking comparisons')]) +
        '\nPNGs are 300 dpi. PDFs embed the font; SVG lettering is outlined so its '
        'appearance does not depend on installed fonts. Change wording in the plotting '
        'source and rebuild, rather than expecting the SVG lettering to remain editable text.\n\n'
        'Exact values are in data/. Numerical figures keep realized original/retained '
        'context-token ratios and circle/square/triangle markers for requested 1.10x/1.25x/2.00x '
        'targets. The 0-to-1 score scale is zoomed differently in each figure: outcome '
        '0.545-0.635, reasoning 0.400-0.565, legal basis 0.395-0.635. Compare numerical '
        'ticks, not slopes across panels. The uncompressed and paragraph-ID references '
        'remain; the no-context line and methodological footer remain omitted. Paragraph '
        'IDs are still a privileged, non-deployable ground-truth control.\n\n'
        'Ranking bars retain all 526 primary questions per condition, with the original '
        '128 and additional 398 blocks verified separately. These are compressed-versus-raw '
        'relations extracted from four-answer judgments, not a direct method leaderboard. '
        'The extension is post-results and descriptive. Reliability repeats are not additional '
        'primary observations. Percentage labels may round to 99.9 or 100.1 in total.\n\n'
        'No scores, counts or scientific inputs were changed. No error bars are drawn. '
        'The original paired pointwise 95% context-cluster intervals remain in the score '
        'CSV; they describe differences versus raw, not absolute-score uncertainty. '
        'Neither numerical means nor rankings establish no-loss, non-inferiority, human '
        'validation or retained-statute grounding.\n\n'
        'Rebuild with `legal-repro figures --output outputs/figures-NEW`.\n'
        'This reconstruction reads verified archived evidence; it runs no models.\n')
    scripts = ('build_figures.py', 'figure_style.py', 'plot_score_dimensions.py', 'plot_rankings.py')
    files = [f'{name}.{extension}' for name in PLOT_NAMES for extension in FORMATS]
    files += [f'data/{name}' for name in tables] + ['README.md']
    font_path = Path(findfont(FontProperties(family=FONT_FAMILY), fallback_to_default=False))
    verification = {
        'accepted': True, 'created_at': datetime.now(timezone.utc).isoformat(),
        'plot_names': list(PLOT_NAMES), 'formats': list(FORMATS),
        'source_manifest_sha256': scores.MANIFEST_SHA, 'source_sha256': source_bindings,
        'scripts_sha256': {name: scores.sha(Path(__file__).parent / name) for name in scripts},
        'font_family': FONT_FAMILY, 'font_file': font_path.name, 'font_sha256': scores.sha(font_path),
        'font_weight': 'normal', 'palette': PALETTE,
        'title_drawn': False, 'requested_target_panel_labels_drawn': True,
        'font_sizes_pt_by_plot': {
            **{metric: SCORE_FONT_SIZES for metric in scores.METRICS},
            'ranking_comparisons': {'axis_labels': AXIS_LABEL_SIZE, 'ticks': TICK_LABEL_SIZE,
                                   'legends': LEGEND_SIZE, 'annotations': ANNOTATION_SIZE,
                                   'ranking_panel_labels': PANEL_LABEL_SIZE}},
        'ranking_colors': {key: value[1] for key, value in rankings.RELATIONS.items()},
        'svg_text_outlined': True, 'pdf_fonts_embedded': True, 'png_dpi': 300,
        'python_version': sys.version.split()[0], 'matplotlib_version': matplotlib.__version__,
        'numerical_points_verified': len(points), 'reference_lines_verified': len(controls),
        'ranking_bars_verified': len(rank_rows), 'ranking_segments_verified': 3 * len(rank_rows),
        'target_marker_mapping': {f'{ratio:.2f}': marker for ratio, marker in scores.TARGET_MARKERS.items()},
        'score_x_limits': list(scores.X_LIMITS),
        'score_y_limits': {metric: list(axis[:2]) for metric, axis in scores.Y_AXES.items()},
        'font_and_text_bounds_checked': True, 'footer_drawn': False,
        'source_evidence_modified': False, 'gpu_actions': False,
        'output_sha256': {name: scores.sha(output / name) for name in files},
    }
    (output / 'verification.json').write_text(json.dumps(verification, indent=2) + '\n')
    print(json.dumps({'output': str(output), 'plots': len(PLOT_NAMES), 'formats': list(FORMATS),
                      'font': FONT_FAMILY, 'numerical_points': len(points), 'ranking_bars': len(rank_rows)}))
    return verification





