"""Apply the documented portability changes to a fresh allowlisted export."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'src/legal_repro'


def replace_function(text, name, replacement):
    node = next(n for n in ast.parse(text).body if isinstance(n,ast.FunctionDef) and n.name==name)
    lines=text.splitlines(keepends=True)
    return ''.join(lines[:node.lineno-1])+replacement+'\n'+''.join(lines[node.end_lineno:])


def without_main(text):
    nodes=[n for n in ast.parse(text).body if isinstance(n,ast.If) and '__name__' in ast.get_source_segment(text,n.test)]
    for node in reversed(nodes):
        lines=text.splitlines(keepends=True)
        text=''.join(lines[:node.lineno-1])+''.join(lines[node.end_lineno:])
    return text


path=PACKAGE/'review_bundle.py'
text=path.read_text()
start=text.index('WORKSPACE = ')
end=text.index('METHODS = ',start)
text=text[:start]+'from .paths import ASSETS\nWORKSPACE = ASSETS\n'+text[end:]
text=replace_function(text,'load_payload','def load_payload() -> dict:\n    from .bundle import load_payload as load\n    return load()')
start=text.index('    if Path.cwd().resolve() != WORKSPACE:',text.index('def build('))
end=text.index('    payload = load_payload()',start)
text=text[:start]+'''    absolute = output.expanduser().absolute()
    resolved = absolute.resolve()
    if resolved != absolute or resolved.exists() or resolved.is_relative_to(ASSETS):
        raise PermissionError("Use a fresh non-symlink output outside packaged resources")
'''+text[end:]
text=text.replace('help="Fresh child of review/"','help="Fresh output directory"')
path.write_text(text)

path=PACKAGE/'expert_review.py'
text=path.read_text()
text=replace_function(text,'fresh_path','''def fresh_path(path: Path) -> Path:
    from .paths import ASSETS
    absolute = path.expanduser().absolute()
    resolved = absolute.resolve()
    if resolved == ASSETS or resolved.is_relative_to(ASSETS) or absolute != resolved or path.exists():
        raise PermissionError("Use a fresh non-symlink path outside packaged resources")
    return resolved
''')
path.write_text(text)

for name in ('plot_score_dimensions','plot_rankings','build_figures'):
    path=PACKAGE/(name+'.py')
    text=path.read_text().replace('from figure_style import','from .figure_style import').replace('from plot_score_dimensions import','from .plot_score_dimensions import')
    text=text.replace('import plot_score_dimensions as scores','from . import plot_score_dimensions as scores').replace('import plot_rankings as rankings','from . import plot_rankings as rankings')
    text=text.replace("REPO = Path('/home/prioma/code/ma_contextcompression_minimal')",'from .paths import ASSETS\nREPO = ASSETS')
    text=text.replace("SOURCE = REPO / 'paper/full526-20260907T041200Z'","SOURCE = REPO / 'paper'")
    text=text.replace("sha(REPO / 'paper/figure_style.py')","sha(Path(__file__).with_name('figure_style.py'))")
    text=without_main(text)
    if name in ('plot_score_dimensions','plot_rankings'):
        text=replace_function(text,'build','')
    else:
        text=replace_function(text,'publish_final','')
        old="    output = output.resolve()\n    if Path.cwd().resolve() != REPO or not output.is_relative_to(REPO / 'paper/figures') or output.exists():\n        raise PermissionError('Use a fresh child of paper/figures in the named repository')"
        assert old in text
        text=text.replace(old,"    absolute = output.expanduser().absolute()\n    output = absolute.resolve()\n    if absolute != output or output.exists() or output.is_relative_to(scores.REPO):\n        raise PermissionError('Use a fresh output directory outside packaged resources')")
        begin=text.index("        'Reproduce from /home/prioma/")
        end=text.index("    scripts = ",begin)
        text=text[:begin]+"        'Rebuild with `legal-repro figures --output outputs/figures-NEW`.\\n'\n        'This reconstruction reads verified archived evidence; it runs no models.\\n')\n"+text[end:]
    path.write_text(text)

for path in (ROOT/'tests').glob('test_*.py'):
    text=path.read_text().replace('legal_pruning','legal_repro')
    text=text.replace('ASSETS.parents[1] / "tests/expert_review_dom.cjs"','Path(__file__).parent / "expert_review_dom.cjs"')
    text=text.replace('ASSETS.parents[1] / "tests/expert_pairwise_dom.cjs"','Path(__file__).parent / "expert_pairwise_dom.cjs"')
    text=text.replace('ASSETS.parents[1] / "tests/expert_completion_dom.cjs"','Path(__file__).parent / "expert_completion_dom.cjs"')
    path.write_text(text)

print('Ported resource paths, output guards and package imports; scientific rendering and human-study logic retained.')
