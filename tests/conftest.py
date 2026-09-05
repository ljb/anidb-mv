import pytest

from amv.file_info import FileInfo


@pytest.fixture(autouse=True)
def isolated_home(monkeypatch, tmp_path):
    """
    Points HOME and the XDG variables at a throwaway directory for every test.

    Without this the suite reads the developer's real ~/.amvrc and ~/.amv.sqlite3.
    That is how the amv-db tests passed locally while failing in CI: they patched
    the wrong module, fell through to the real read_config(), and found a config
    file that only exists on a developer's machine.
    """
    for variable in ("HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME"):
        monkeypatch.setenv(variable, str(tmp_path / variable.lower()))


def create_file_info(path, id_=None):
    return FileInfo(
        id=id_,
        view_date=1532983833.2112887,
        internal=True,
        watched=True,
        path=path,
        size=1337,
        ed2k="1" * 32,
    )
