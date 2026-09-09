# Final plots

Use this folder for the four current plots. All use STIXGeneral serif type, no overall titles, the same 12-inch export width, and a shared purple-blue-teal-green-yellow palette. Ranking colors are drawn from that palette: purple = below uncompressed, blue = tied, green = above uncompressed. Method colors in the score plots retain their previous meanings. Score-figure axis labels are 19 pt; their legends, tick labels and reference labels are 17 pt, with a two-row method legend. Ranking typography is unchanged: the axis label is 15 pt, legends, ticks and percentages are 13 pt, and requested-target panel labels are 14 pt.

| Plot | Image | Vector | Paper-ready |
| --- | --- | --- | --- |
| Outcome correctness | [PNG](outcome_correctness.png) | [SVG](outcome_correctness.svg) | [PDF](outcome_correctness.pdf) |
| Legal reasoning correctness | [PNG](legal_reasoning_correctness.png) | [SVG](legal_reasoning_correctness.svg) | [PDF](legal_reasoning_correctness.pdf) |
| Legal basis correctness | [PNG](legal_basis_correctness.png) | [SVG](legal_basis_correctness.svg) | [PDF](legal_basis_correctness.pdf) |
| Ranking comparisons | [PNG](ranking_comparisons.png) | [SVG](ranking_comparisons.svg) | [PDF](ranking_comparisons.pdf) |

PNGs are 300 dpi. PDFs embed the font; SVG lettering is outlined so its appearance does not depend on installed fonts. Change wording in the plotting source and rebuild, rather than expecting the SVG lettering to remain editable text.

Exact values are in data/. Numerical figures keep realized original/retained context-token ratios and circle/square/triangle markers for requested 1.10x/1.25x/2.00x targets. The 0-to-1 score scale is zoomed differently in each figure: outcome 0.545-0.635, reasoning 0.400-0.565, legal basis 0.395-0.635. Compare numerical ticks, not slopes across panels. The uncompressed and paragraph-ID references remain; the no-context line and methodological footer remain omitted. Paragraph IDs are still a privileged, non-deployable ground-truth control.

Ranking bars retain all 526 primary questions per condition, with the original 128 and additional 398 blocks verified separately. These are compressed-versus-raw relations extracted from four-answer judgments, not a direct method leaderboard. The extension is post-results and descriptive. Reliability repeats are not additional primary observations. Percentage labels may round to 99.9 or 100.1 in total.

No scores, counts or scientific inputs were changed. No error bars are drawn. The original paired pointwise 95% context-cluster intervals remain in the score CSV; they describe differences versus raw, not absolute-score uncertainty. Neither numerical means nor rankings establish no-loss, non-inferiority, human validation or retained-statute grounding.

Reproduce from /home/prioma/code/ma_contextcompression_minimal into a fresh folder:

```bash
CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 python3 paper/build_figures.py --output paper/figures/FRESH_DIRECTORY
```

Add `--refresh-final` to publish a verified, styling-only rebuild to `paper/figures/final/`. Before replacement, its existing generated files are copied to `previous_final.zip` inside the fresh build directory. No existing file is deleted or moved.

The builder reads the pinned paper evidence and never loads models. verification.json binds the source data, plotting code, font file and all outputs. figure_style.py is the shared style definition. Earlier figure exports, papers and accepted experiment evidence are preserved.
