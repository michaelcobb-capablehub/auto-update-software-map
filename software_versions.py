#!/usr/bin/env python3

import os
import re

from git_source import *
from version import *

#
# Whole repository operations
#


#
# Initialisation functions - for handling the configurations of a particular project
#

def init_source(type, url, source_opts=None):
    """
    Handles the "source" part of the project's configuration.
    Currently accepted sources are
      -  Git repository

    Returns the pygit2 object that represents the Git repository
    """
    if type == "git":
        return make_git_source(url, source_opts)
    else:
        raise RuntimeError(f"Invalid source type: {type}")

def get_repo_version(src_repo, version_matcher):
    r = version_matcher["fn"](src_repo, *version_matcher["args"])
    version_type = version_matcher.get("version_type")
    if r is None:
        return None
    commit, version = r
    return (commit, make_version(version_type, version) if version is not None else None)

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
