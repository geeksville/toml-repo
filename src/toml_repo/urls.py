"""Canonical ``file://`` URL handling.

A repository is identified by its URL: it is written into config files and
databases and compared for equality, so there must be exactly one spelling for
"this directory on this machine".  That spelling is what
:meth:`pathlib.Path.as_uri` produces::

    file:///home/user/data             POSIX
    file:///C:/Users/user/data         Windows: the drive is a path segment
    file:////server/share/data         Windows UNC share

Hand-building ``f"file://{path}"`` is *not* equivalent.  On Windows it yields
``file://C:\\Users\\data``, which puts the whole filesystem path in the URL
authority, so the rest of the URL (and any consumer that reads ``url[7:]`` or
:func:`urllib.parse.urlsplit`) silently gets a different, relative path.
:func:`path_from_file_url` therefore rejects that legacy spelling outright
instead of guessing which path was meant.
"""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

#: A canonical drive-letter path segment, e.g. the ``/C:/`` of ``file:///C:/data``.
_DRIVE_SEGMENT = re.compile(r"^/[A-Za-z]:(?:/|$)")

#: URL hosts that mean "this machine", i.e. no host at all.
_LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1"})


def _not_canonical(url: str, why: str) -> ValueError:
    """The error for a URL that is not in canonical form, explaining ``why``."""
    return ValueError(
        f"file:// URL is not canonical: {url!r}.  {why}.  Build file URLs with "
        f"make_file_url() (i.e. Path.as_uri()), which gives 'file:///C:/data' "
        f"and never 'file://C:\\data'."
    )


def make_file_url(path: Path | str) -> str:
    """Return the canonical ``file://`` URL naming a filesystem path.

    This is the only supported way to build a file URL (and the reason this
    library does not accept the hand-built ``file://C:\\dir`` form): it is
    correct for backslashes, drive letters, UNC shares, spaces and non-ASCII
    characters on every platform.

    Args:
        path: The path to encode.  A relative path is resolved first, since
            ``Path.as_uri()`` refuses relative paths and a URL that cannot be
            opened helps no caller.

    Returns:
        The canonical URL, e.g. ``file:///home/user/data``.
    """
    path_ = Path(path)
    if not path_.is_absolute():
        path_ = path_.resolve()
    return path_.as_uri()


def path_from_file_url(url: str) -> Path:
    """Return the filesystem path named by a canonical ``file://`` URL.

    The inverse of :func:`make_file_url`: percent-encoding is decoded and the
    URL's spelling of a Windows drive letter is mapped back to the one ``Path``
    expects.  Parsing is deliberately platform-independent (a Windows path URL
    yields a Windows path even when parsed on POSIX), so it can be tested
    anywhere.

    Args:
        url: The URL to parse.

    Returns:
        The path the URL names.

    Raises:
        ValueError: If ``url`` is not a ``file://`` URL, or is not in canonical
            form: either the legacy hand-built spelling (``file://C:\\data``) or
            a relative-path form (``file:data``).  Neither can be told apart
            from a host or resolved to a real file, so the only sane answer is
            to refuse them -- guessing would silently resolve to a path that
            does not exist.
    """
    parsed = urlsplit(url)
    if parsed.scheme != "file":
        raise ValueError(f"Not a file:// URL: {url!r}")

    host = parsed.netloc
    if host.lower() in _LOCAL_HOSTS:
        # "file://localhost/data" is just "file:///data".
        host = ""

    if host:
        if "\\" in host or _DRIVE_SEGMENT.match(f"/{host}"):
            raise _not_canonical(url, "its host is a filesystem path, not a machine name")
        if not parsed.path.startswith("/"):
            raise _not_canonical(url, "its path is relative, not absolute")
        # A UNC share written with a host: file://server/share/data.
        path = f"//{host}{parsed.path}"
    elif _DRIVE_SEGMENT.match(parsed.path):
        # file:///C:/data -> C:/data.  Matching the *still encoded* path is
        # deliberate: a POSIX directory that really is named "/C:" has its
        # colon percent-encoded by as_uri() ("file:///C%3A/x"), so only a
        # Windows drive letter can match here.
        path = parsed.path[1:]
    else:
        if not parsed.path.startswith("/"):
            # A canonical file URL always has an absolute path.  Anything else
            # (e.g. the "file:%5C%5C%5Ctmp" Qt produces for the legacy
            # "file:\\\tmp" spelling) is not a path on any machine, and reading
            # it as a relative path would resolve against the CWD -- which
            # "exists", so callers would silently get the wrong answer.
            raise _not_canonical(url, "its path is relative, not absolute")
        path = parsed.path

    return Path(unquote(path))
