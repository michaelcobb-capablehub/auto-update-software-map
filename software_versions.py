#!/usr/bin/env python3

import os
import re

from git_source import *
from version import *

#
# Whole repository operations
#

def get_repo_fork_point(upstream, fork):
    """
    Returns the first commit from the currently checked-out branch in `fork` that also appears in
    the currently checked-out branch in `upstream`.

    This represents the point at which `fork` divereged from `upstream`.
    """
    for commit_frk in fork.walk(fork.head.target, pygit2.enums.SortMode.TOPOLOGICAL):
        commit_ups = upstream.get(commit_frk.id)
        if commit_ups is not None:
            return commit_ups
    return None

#
# Initialisation functions - for handling the configurations of a particular project
#

def init_source(conf):
    """
    Handles the "source" part of the project's configuration.
    Currently accepted sources are
      -  Git repository

    Returns the pygit2 object that represents the Git repository
    """
    if "git" in conf:
        git_source = conf["git"]
        branch = git_source.get("branch")
        remote = git_source.get("remote")

        repo = init_git_repo(remote, branch)
        return { "repo": repo, "branch": branch, "remote": remote }
    else:
        raise RuntimeError(f"Error: No valid sources in: {list(conf.keys())}")

def get_repo_version(repo, conf_matcher):
    r = conf_matcher["fn"](repo, *conf_matcher["args"])
    version_type = conf_matcher.get("version_type")
    if r is None:
        return None
    commit, version = r
    return (commit, make_version(version_type, version) if version is not None else None)

def find_repo_version(src, version_matcher):
    src_repo = src.get("repo")
    for method in version_matcher:
        r = get_repo_version(src_repo, method)
        if r is not None:
            return r

def find_repo_fork_upstream_version(upstream_src, fork_src, version_matcher):
    upstream_repo = upstream_src.get("repo")

    fork_repo = fork_src.get("repo")

    diverge_commit = get_repo_fork_point(upstream_repo, fork_repo)
    #print("Fork diverged at:", diverge_commit)
    checkout_commit(upstream_repo, diverge_commit)
    for method in version_matcher:
        r = get_repo_version(upstream_repo, method)
        if r is not None:
            return (diverge_commit, r)
    return None
