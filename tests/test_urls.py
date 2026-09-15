"""Tests for the canonical ``file://`` URL helpers (``toml_repo.urls``)."""

import sys
from pathlib import Path, PureWindowsPath

import pytest

from toml_repo import Repo, make_file_url, path_from_file_url


def test_make_file_url_round_trips_a_real_directory(tmp_path: Path):
    """The two helpers are exact inverses for a path that exists."""
    (tmp_path / "cam").mkdir()
    (tmp_path / "cam" / "master.fit").touch()

    url = make_file_url(tmp_path / "cam")

    assert url.startswith("file:///")
    assert "\\" not in url
    assert path_from_file_url(url) == tmp_path / "cam"
    # A Repo built from the same path agrees, and can resolve through it.
    assert Repo(tmp_path / "cam").url == url
    assert Repo(url).get_path() == tmp_path / "cam"
    assert Repo(url).resolve_path("master.fit") == tmp_path / "cam" / "master.fit"


def test_make_file_url_resolves_a_relative_path(tmp_path: Path, monkeypatch):
    """``as_uri()`` refuses a relative path, and a URL nothing can open is useless."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "frame.fits").touch()

    url = make_file_url(Path("frame.fits"))

    assert url.startswith("file:///")
    assert path_from_file_url(url) == tmp_path / "frame.fits"


def test_make_file_url_encodes_spaces_and_non_ascii(tmp_path: Path):
    """Neither a space nor a non-ASCII character ends up raw in the URL."""
    odd = tmp_path / "my data" / "café"
    odd.mkdir(parents=True)

    url = make_file_url(odd)

    assert " " not in url
    assert "café" not in url
    assert path_from_file_url(url) == odd


def test_path_from_file_url_reads_a_windows_drive_letter():
    """``file:///C:/dir`` is a drive path, not a path on the current drive.

    Parsed on POSIX too: the conversion itself is platform-independent, which is
    what lets CI catch a Windows regression.
    """
    path = path_from_file_url("file:///C:/Users/runner/data")

    assert str(path) == "C:/Users/runner/data"
    assert PureWindowsPath(str(path)).drive == "C:"
    assert PureWindowsPath(str(path)).is_absolute()


@pytest.mark.skipif(
    sys.platform != "win32",
    reason="POSIX Path normalises 'C:/' to the relative 'C:' -- a Windows drive "
    "root can only be represented by a Windows Path (CI runs this on Windows).",
)
def test_path_from_file_url_reads_a_windows_drive_root():
    """A whole drive root (``file:///D:/``, e.g. a photo library) keeps its root.

    This matters for real URLs: ``file:///D:/`` must not degrade to the
    *drive-relative* ``D:`` (which means "current directory on D:"), so the
    drive separator has to survive the trip.
    """
    path = path_from_file_url("file:///D:/")

    assert PureWindowsPath(path).parts == ("D:\\",)
    assert PureWindowsPath(path).is_absolute()


def test_path_from_file_url_handles_a_windows_unc_share():
    """Both spellings of a UNC share name the same server path.

    ``Path.as_uri()`` writes a UNC path as ``file:////server/share`` (an empty
    host and a path that starts with two slashes), while a hand-written URL
    puts the server in the host position.  Both must land on the same path.
    """
    from_as_uri = path_from_file_url("file:////server/share/data")
    from_host = path_from_file_url("file://server/share/data")

    assert str(from_as_uri) == str(from_host)
    assert str(PureWindowsPath(str(from_host))) == "\\\\server\\share\\data"


def test_path_from_file_url_ignores_a_localhost_host():
    """``file://localhost/data`` means ``file:///data`` -- the host is this machine."""
    assert str(path_from_file_url("file://localhost/data")) == "/data"
    assert str(path_from_file_url("file://127.0.0.1/data")) == "/data"


def test_path_from_file_url_decodes_percent_encoding():
    """Encoded characters (as ``as_uri()`` writes them) come back verbatim."""
    assert str(path_from_file_url("file:///a%20b/c%26d")) == "/a b/c&d"


def test_path_from_file_url_keeps_a_posix_directory_that_looks_like_a_drive():
    """A POSIX "/C:" directory must not be mistaken for a Windows drive.

    ``as_uri()`` percent-encodes the colon of a POSIX path, so matching the
    drive pattern against the encoded path is what keeps the two apart.
    """
    assert str(path_from_file_url("file:///C%3A/x")) == "/C:/x"


@pytest.mark.parametrize(
    "url",
    [
        "file://C:\\Users\\runner\\data",
        "file://C:/Users/runner/data",
        "file://c:/data",
    ],
    ids=["backslashes", "forward-slashes", "lowercase-drive"],
)
def test_path_from_file_url_rejects_the_legacy_hand_built_form(url: str):
    """The old ``f"file://{path}"`` spelling is refused, not silently misread.

    Its filesystem path sits in the URL *authority*, so nothing distinguishes it
    from a host: reading it as a UNC share would resolve the real ``C:\\...``
    path to something that does not exist.
    """
    with pytest.raises(ValueError, match="not canonical"):
        path_from_file_url(url)


@pytest.mark.parametrize("url", ["pkg://defaults", "https://example.com/repo", "nonsense"])
def test_path_from_file_url_rejects_a_non_file_url(url: str):
    """A non-file scheme has no local path."""
    with pytest.raises(ValueError, match="Not a file:// URL"):
        path_from_file_url(url)


def test_repo_refuses_a_legacy_url_instead_of_reading_the_wrong_directory():
    """A hand-built Windows URL fails loudly rather than loading the wrong repo.

    ``Repo("file://C:\\Users\\runner\\data")`` used to resolve to the *relative*
    path ``C:\\Users\\runner\\data`` -- the filesystem path became the URL
    authority -- so it quietly loaded an empty config from the current
    directory instead of the real repository.
    """
    with pytest.raises(ValueError, match="not canonical"):
        Repo("file://C:\\Users\\runner\\data")

    # The canonical spelling of the very same path is accepted (it need not
    # exist: a missing config is not an error, a misread one is).
    assert Repo("file:///C:/Users/runner/data").url == "file:///C:/Users/runner/data"
