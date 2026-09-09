"""One print-oriented font, palette and export policy for the current figures."""
from functools import wraps
from pathlib import Path


FONT_FAMILY = 'STIXGeneral'  # Bundled with Matplotlib; no system-font download.
FIGURE_WIDTH = 12.0
AXIS_LABEL_SIZE = 15
TICK_LABEL_SIZE = 13
LEGEND_SIZE = 13
ANNOTATION_SIZE = 13
PANEL_LABEL_SIZE = 14
INK = '#222222'
AXIS_COLOR = '#b6b6b6'
GRID_COLOR = '#e8e8e8'
PALETTE = {
    'purple': '#440154', 'blue': '#31688e', 'teal': '#21918c',
    'green': '#35b779', 'yellow': '#fde725',
}
FORMATS = ('png', 'svg', 'pdf')
RC_PARAMS = {
    'font.family': FONT_FAMILY, 'font.size': ANNOTATION_SIZE, 'font.weight': 'normal',
    'axes.titlesize': PANEL_LABEL_SIZE, 'axes.titleweight': 'normal',
    'axes.labelsize': AXIS_LABEL_SIZE, 'axes.labelweight': 'normal',
    'text.color': INK, 'axes.labelcolor': INK,
    'xtick.color': '#444444', 'ytick.color': '#444444',
    'xtick.labelsize': TICK_LABEL_SIZE, 'ytick.labelsize': TICK_LABEL_SIZE,
    'legend.fontsize': LEGEND_SIZE, 'legend.title_fontsize': LEGEND_SIZE,
    'mathtext.fontset': 'stix', 'figure.facecolor': 'white',
    'savefig.facecolor': 'white', 'savefig.dpi': 300,
    # Outlined SVG text and embedded PDF fonts preserve appearance on other machines.
    'svg.fonttype': 'path', 'pdf.fonttype': 42, 'ps.fonttype': 42,
}
SCORE_FONT_INCREASE = 4
SCORE_FONT_SIZES = {
    'axis_labels': AXIS_LABEL_SIZE + SCORE_FONT_INCREASE,
    'ticks': TICK_LABEL_SIZE + SCORE_FONT_INCREASE,
    'legends': LEGEND_SIZE + SCORE_FONT_INCREASE,
    'annotations': ANNOTATION_SIZE + SCORE_FONT_INCREASE,
}
SCORE_RC_PARAMS = {key: RC_PARAMS[key] + SCORE_FONT_INCREASE for key in (
    'font.size', 'axes.titlesize', 'axes.labelsize', 'xtick.labelsize',
    'ytick.labelsize', 'legend.fontsize', 'legend.title_fontsize')}


def styled(draw=None, *, overrides=None):
    """Apply the same style to CLI builds and direct/test rendering, without leaks."""
    if draw is None:
        return lambda function: styled(function, overrides=overrides)
    @wraps(draw)
    def wrapped(*args, **kwargs):
        import matplotlib
        from matplotlib.font_manager import FontProperties, findfont

        findfont(FontProperties(family=FONT_FAMILY), fallback_to_default=False)
        with matplotlib.rc_context({**RC_PARAMS, **(overrides or {})}):
            return draw(*args, **kwargs)
    return wrapped


def save_plot(fig, output: Path, name: str, labels) -> None:
    """Check actual text/geometry, then export matching raster and vector figures."""
    from matplotlib.text import Text

    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    for text in fig.findobj(Text):
        if text.get_visible() and text.get_text():
            if text.get_fontproperties().get_name() != FONT_FAMILY:
                raise ValueError('A figure label does not use the shared serif font')
            if text.get_weight() != 'normal':
                raise ValueError('A figure label unexpectedly uses bold type')
    for label in labels:
        bounds = label.get_window_extent(renderer)
        if bounds.x0 < 0 or bounds.y0 < 0 or bounds.x1 > fig.bbox.width or bounds.y1 > fig.bbox.height:
            raise ValueError('Figure text or legend would be clipped')
    for extension in FORMATS:
        metadata = {'Date': None} if extension == 'svg' else None
        if extension == 'pdf':
            metadata = {'CreationDate': None, 'ModDate': None}
        fig.savefig(output / f'{name}.{extension}', metadata=metadata)
