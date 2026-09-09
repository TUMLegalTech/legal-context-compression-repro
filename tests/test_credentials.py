import pytest
from legal_repro.runner import api_key


def test_exact_ignored_key_file_and_environment_precedence(monkeypatch,tmp_path):
    contract={'WORKSPACE':str(tmp_path),'API_KEY_ENV':'OPENROUTER_API_KEY'}
    monkeypatch.delenv('OPENROUTER_API_KEY',raising=False)
    with pytest.raises(ValueError,match='Set OPENROUTER_API_KEY'):
        api_key(contract)
    (tmp_path/'.env').write_text('OPENROUTER_API_KEY="synthetic-key"\n')
    assert api_key(contract)=='synthetic-key'
    monkeypatch.setenv('OPENROUTER_API_KEY','synthetic-environment-key')
    assert api_key(contract)=='synthetic-environment-key'
    monkeypatch.delenv('OPENROUTER_API_KEY')
    (tmp_path/'.env').write_text('UNRELATED=value\n')
    with pytest.raises(ValueError,match='one OPENROUTER_API_KEY'):
        api_key(contract)
