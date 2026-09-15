"""
The toml_repo package provides a generic TOML-based repository manager.

It handles finding, loading, merging, and searching TOML configuration repositories
with support for multiple URL schemes (file://, pkg://, http://), import resolution,
and precedence-based configuration merging.

``file://`` URLs are canonical: build them with :func:`make_file_url` (or
``Path.as_uri()``) and parse them with :func:`path_from_file_url`, never by
string concatenation or slicing -- see :mod:`toml_repo.urls` for why.
"""

from .manager import RepoManager
from .repo import REPO_REF, Repo, get_config_suffix, set_config_suffix, set_pkg_resource_root
from .urls import make_file_url, path_from_file_url

__all__ = [
    "RepoManager",
    "Repo",
    "get_config_suffix",
    "set_config_suffix",
    "set_pkg_resource_root",
    "make_file_url",
    "path_from_file_url",
    "REPO_REF",
]
