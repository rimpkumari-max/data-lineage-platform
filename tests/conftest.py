import pytest


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setenv("LINEAGE_DB", str(tmp_path / "test.db"))
