#!/usr/bin/env python3

import os
import re

from git_source import *
from version import *

def init_source(source_type, url, source_opts=None):
    """
    Handles the "source" part of the project's configuration.
    Currently accepted sources are
      -  Git repository

    Returns the pygit2 object that represents the Git repository
    """

    if source_type == "git":
        return make_git_source(url, source_opts)
    else:
        raise RuntimeError(f"Invalid source type: {source_type}")

def get_repo_version(src_repo, version_matcher):
    r = version_matcher["fn"](src_repo, *version_matcher["args"])
    if r is None:
        return None
    commit, raw_version = r
    version_type = version_matcher.get("version_type")
    version = make_version(version_type, raw_version) if raw_version is not None else None
    logging.info(f"Matched commit {commit.id} to version '{version}' using method '{version_matcher['method']}'")
    return (commit, version)

def find_repo_version(src_repo, version_matcher):
    for method in version_matcher:
        r = get_repo_version(src_repo, method)
        if r is not None:
            return r

def find_repo_fork_upstream_version(upstream_src, fork_src, version_matcher):
    diverge_commit = upstream_src.get_repo_fork_point(fork_src)
    #print("Fork diverged at:", diverge_commit)
    upstream_src.checkout_commit(diverge_commit)
    for method in version_matcher:
        r = get_repo_version(upstream_src, method)
        if r is not None:
            return (diverge_commit, r)
    return None
