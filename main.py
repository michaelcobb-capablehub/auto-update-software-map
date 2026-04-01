#!/usr/bin/env python3

import os
import re

from git_source import *

#DEBUG = True
DEBUG = False

CHECKOUT_SUBDIR="repos"

#
# Common helper functions
#

def collect_match_group(groupindex, match):
    """
    Collects named capture groups from the regex match `match` into a dict, where each key is given by the
    regex group index in `groupindex`.
    """
    return { k: match.group(v) for k, v in groupindex.items() }

def commit_in_branch(repo, branch, commit):
    """
    Returns True if the Git `commit` is contained within the `branch`. False otherwise.
    """
    branch_commit = branch.peel(pygit2.Commit)
    return repo.descendant_of(branch_commit.id, commit.id)

#
# Internal versions of the "top level" functions below.
# Operate only on the currently checked-out branch.
#

def __match_file(repo, file_path, matchers):
    """
    Matches each line of the file `file_path` within the Git repository `repo` by the array of regexs in `matchers`.
    Each match is converted to a dict using `collect_match_group()` then all matches are flattened into a single dict.

    Returns a tuple containing:
        (current commit object, regex match).
    """
    abspath = os.path.join(repo.workdir, file_path)
    matches = []

    commit_ref = repo.head.peel(pygit2.Commit)

    try:
        with open(abspath, "r") as f:
            for line_num, line in enumerate(f):
                for r in matchers:
                    match = r.search(line)
                    if match:
                        matches.append(collect_match_group(r.groupindex, match))
    except Exception as ex:
        print(f"Exception while processing file: {file_path}:", ex)

    # Flatten array of dicts into a single dict
    all_matches = {}
    for m in matches:
        all_matches.update(m)
    return (commit_ref, all_matches)

def __latest_matching_tag(repo, regex):
    """
    Walks commits in the current Git `repo` in topological order, and finds the most recent commit which
    includes a tag matching the given `regex`.

    Returns a nested tuple containing:
        (tagged commit object, `regex` match)
    """
    result = None

    tag_map = {}
    for ref in repo.references.iterator(pygit2.GIT_REFERENCES_TAGS):
        commit = ref.peel(pygit2.Commit)
        tag_map.setdefault(commit, []).append(ref)

    for commit in repo.walk(repo.head.peel(pygit2.Commit).id, pygit2.GIT_SORT_TOPOLOGICAL):
        is_match = False
        if commit in tag_map:
            commit_tags = tag_map[commit]
            for tag in commit_tags:
                match = regex.match(tag.name)
                if match:
                    result = (commit, collect_match_group(regex.groupindex, match))
                    is_match = True
                    break
        if is_match:
            break

    return result


#
# "top level" functions intended to be used by project "configurations" to perform extraction of version info from the repository.
#

def latest_matching_tag(repo, match_regex):
    """
    For each remote branch in the `repo`, check it out, then return the most recent commit which contains a tag
    that matches the regex given by `match_regex`.
    """
    compiled_regex = re.compile(match_regex)
    #return for_all_remote_branches(repo, __latest_matching_tag, [compiled_regex])
    return __latest_matching_tag(repo, compiled_regex)

def match_file(repo, file_path, match_regexes):
    """
    For each remote branch in the `repo`, check it out, then match each regex in the `match_regexes` array against the file
    path specified by `file_path` inside the repo.
    """
    # compile the regexes
    compiled_regexes = [re.compile(x) for x in match_regexes]
    #return for_all_remote_branches(repo, __match_file, [file_path, compiled_regexes])
    return __match_file(repo, file_path, compiled_regexes)

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

def init_source(conf_source):
    """
    Handles the "source" part of the project's configuration.
    Currently accepted sources are
      -  Git repository

    Returns the pygit2 object that represents the Git repository
    """
    if "git" in conf_source:
        git_source = conf_source["git"]
        branch = git_source.get("branch")
        remote = git_source.get("remote")
        # TODO: Should probably use the repo name to decide where to clone the git repo, just like real git does
        checkout_dir = None
        if "checkout_dir" in git_source:
            checkout_dir = os.path.join(os.path.curdir, CHECKOUT_SUBDIR or "", git_source.get("checkout_dir"))
        repo = init_git_repo(remote, checkout_dir, branch)
        return { "repo": repo, "branch": branch, "remote": remote }
    else:
        raise RuntimeError(f"Error: No valid sources in: {list(conf_source.keys())}")

def get_origin_branch_ref(repo, branch_name, origin=None):
    remote_origin = None

    lookup_origin = origin or "origin"

    if lookup_origin in repo.remotes:
        remote_origin = origin
    elif origin is not None:
        raise RuntimeError(f"remote {origin} is not a remote in this repository")
    else:
        remote_origin = repo.remotes[0]

    ref_name = f"{remote_origin.name}/{branch_name}"
    if ref_name in repo.branches.remote:
        return repo.branches.remote.get(ref_name)
    else:
        raise RuntimeError(f"ref {ref_name} does not exist in this repository")

def get_repo_version(repo, conf_matcher):
    return conf_matcher["fn"](repo, *conf_matcher["args"])

def get_all_repo_versions(repo, conf_matcher, remote_branch_names=None):
    """
    Handles the "matcher" part of the project's configuration.

    Returns a function which, when called, will run the provided matcher function with the provided arguments.
    """

    if remote_branch_names is None:
        branch_refs = map(lambda x: repo.branches.remote.get(x), repo.branches.remote)
    else:
        branch_refs = [get_origin_branch_ref(repo, br) for br in remote_branch_names]

    non_symbolic_refs = filter(lambda x: x.type != pygit2.enums.ReferenceType.SYMBOLIC, branch_refs)

    def __wrap_fn(ref):
        checkout_remote_branch(repo, ref)
        return (ref.name, get_repo_version(repo, conf_matcher))

    return map(__wrap_fn, non_symbolic_refs)

#
# Main entry point, called with a project "configuration"
#

def get_fork_matcher(conf, fork_conf):
    if "matcher" in fork_conf:
        return fork_conf["matcher"]
    if "matcher" in conf:
        return conf["matcher"]
    return None

def get_fork_config(conf, fork_name):
    return next(filter(lambda x: x.get("name") == fork_name, conf.get("forks")))

def find_repo_version(conf, fork_name):
    """
    Extract the version of a project given it's configuration `conf`.

    Checks out the repository, and runs the "matcher" function to extract version information from the repository.

    Returns the result of the "matcher" function
    """

    # Find the fork conf with the specified name
    fork_conf = get_fork_config(conf, fork_name)

    conf_source = fork_conf["source"]
    src = init_source(conf_source)
    src_repo = src.get("repo")

    conf_matcher = get_fork_matcher(conf, fork_conf)
    src_remote_branch = src.get("branch")
    remote_branches = [src_remote_branch] if src_remote_branch is not None else None
    return get_all_repo_versions(src_repo, conf_matcher, remote_branch_names=remote_branches)

def find_repo_fork_upstream_version(conf, upstream_fork_name, fork_fork_name):
    conf_upstream = get_fork_config(conf, upstream_fork_name)
    conf_source_u = conf_upstream["source"]
    upstream_src = init_source(conf_source_u)
    upstream_repo = upstream_src.get("repo")

    conf_fork = get_fork_config(conf, fork_fork_name)
    conf_source_f = conf_fork["source"]
    fork_src = init_source(conf_source_f)
    fork_repo = fork_src.get("repo")

    diverge_commit = get_repo_fork_point(upstream_repo, fork_repo)
    #print("Fork diverged at:", diverge_commit)
    checkout_commit(upstream_src.get("repo"), diverge_commit)
    return (diverge_commit, get_repo_version(upstream_src.get("repo"), conf_upstream.get("matcher")))
