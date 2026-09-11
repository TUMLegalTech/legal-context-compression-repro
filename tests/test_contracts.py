import json

import pytest

from legal_repro import contracts, runner
from test_hosted_runner import Fake, Tokenizer


def active_contract(monkeypatch, tmp_path, action='smoke'):
    monkeypatch.chdir(tmp_path)
    path = tmp_path / 'contract.txt'
    contracts.draft(path, tmp_path / 'run', mode=action)
    path.write_text(path.read_text().replace('STATUS: DRAFT', 'STATUS: ACTIVE'))
    return path


@pytest.mark.parametrize('action', ('smoke', 'evaluate'))
def test_api_contract_has_no_github_dependency(monkeypatch, tmp_path, action):
    path = active_contract(monkeypatch, tmp_path, action)
    assert 'GITHUB_' not in path.read_text()
    monkeypatch.setattr(contracts, 'REMOTE', 'https://github.com/example/unrelated.git')
    loaded = contracts.load(path, action)
    assert loaded['ACTION'] == action
    assert loaded['WORKSPACE'] == str(tmp_path)
    assert loaded['API_KEY_ENV'] == 'OPENROUTER_API_KEY'


@pytest.mark.parametrize('remote,visibility', (
    ('https://github.com/mpriorust/legal-context-compression-repro.git', 'private'),
    ('https://github.com/TUMLegalTech/legal-context-compression-repro.git', 'public'),
))
def test_legacy_api_fields_are_preserved_without_restricting_the_destination(monkeypatch, tmp_path, remote, visibility):
    path = active_contract(monkeypatch, tmp_path)
    path.write_text(path.read_text() + f'GITHUB_REMOTE: {remote}\nGITHUB_VISIBILITY: {visibility}\n')
    loaded = contracts.load(path, 'smoke')
    assert loaded['GITHUB_REMOTE'] == remote
    assert loaded['GITHUB_VISIBILITY'] == visibility
    client = Fake()
    result = runner.run(path, backend=client, tokenizer=Tokenizer(), sleep=lambda _: None)
    assert result['kind'] == 'synthetic_transport_test' and len(client.calls) == 18
    manifest = json.loads((tmp_path / 'run/manifest.json').read_text())
    assert manifest['identity']['contract'] == loaded
    resumed = Fake()
    assert runner.run(path, resume=True, backend=resumed, tokenizer=Tokenizer()) == result
    assert resumed.calls == []


@pytest.mark.parametrize('extra', (
    'GITHUB_REMOTE: https://github.com/example/repro.git\n',
    'GITHUB_VISIBILITY: private\n',
    'UNEXPECTED_FIELD: value\n',
))
def test_partial_legacy_or_unknown_fields_fail_before_credentials(monkeypatch, tmp_path, extra):
    path = active_contract(monkeypatch, tmp_path)
    path.write_text(path.read_text() + extra)
    monkeypatch.setattr(runner, 'api_key', lambda _: pytest.fail('Invalid contract reached credential access'))
    with pytest.raises(PermissionError):
        runner.run(path)
    assert not (tmp_path / 'run').exists()


def test_publication_contract_still_requires_the_named_private_destination(monkeypatch, tmp_path):
    path = active_contract(monkeypatch, tmp_path, 'publish')
    loaded = contracts.load(path, 'publish')
    assert loaded['GITHUB_REMOTE'] == contracts.REMOTE
    assert loaded['GITHUB_VISIBILITY'] == 'private'
    path.write_text(path.read_text().replace(contracts.REMOTE, 'https://github.com/example/repro.git'))
    with pytest.raises(PermissionError, match='named private'):
        contracts.load(path, 'publish')


def test_publication_contract_still_rejects_public_visibility(monkeypatch, tmp_path):
    path = active_contract(monkeypatch, tmp_path, 'publish')
    path.write_text(path.read_text().replace('GITHUB_VISIBILITY: private', 'GITHUB_VISIBILITY: public'))
    with pytest.raises(PermissionError, match='named private'):
        contracts.load(path, 'publish')


@pytest.mark.parametrize('legacy', (False, True))
def test_api_contract_cannot_authorize_publication(monkeypatch, tmp_path, legacy):
    path = active_contract(monkeypatch, tmp_path)
    if legacy:
        path.write_text(path.read_text() + f'GITHUB_REMOTE: {contracts.REMOTE}\nGITHUB_VISIBILITY: private\n')
    with pytest.raises(PermissionError):
        contracts.load(path, 'publish')
