#!/usr/bin/env python3

import os
import shutil
from urllib import parse as urllib_parse

import pygit2

CHECKOUT_SUBDIR="repos"

# Skip doing a fresh clone of the repo
SKIP_CLONE = True

def repo_url_to_checkout_path(repo_url):
    parts = urllib_parse.urlsplit(repo_url)
    path = parts.path.strip("/")

    illegal_chars = "./~"
    for c in illegal_chars:
        path = path.replace(c, "_")
    return path

def commit_in_branch(repo, branch, commit):
    """
    Returns True if the Git `commit` is contained within the `branch`. False otherwise.
    """
    branch_commit = branch.peel(pygit2.Commit)
    return repo.descendant_of(branch_commit.id, commit.id)

def get_origin_branch_ref(repo, branch_name, origin=None):
    remote_origin = None

    if branch_name in repo.branches.remote:
        return repo.branches.remote.get(branch_name)

    if origin is not None and origin in repo.remotes:
        ref_name = f"{remote_origin.name}/{branch_name}"
        if ref_name not in repo.branches.remote:
            raise RuntimeError(f"ref {ref_name} does not exist in this repository")
        return repo.branches.get(ref_name)
    else:
        for o in repo.remotes:
            ref_name = f"{o.name}/{branch_name}"
            if ref_name in repo.branches.remote:
                return repo.branches.get(ref_name)
        raise RuntimeError(f"ref {branch_name} does not exist in any remotes in this repository")

def get_repo_remote_branches(repo):
    branch_refs = map(lambda x: repo.branches.remote.get(x), repo.branches.remote)
    non_symbolic_refs = filter(lambda x: x.type != pygit2.enums.ReferenceType.SYMBOLIC, branch_refs)
    return non_symbolic_refs

def checkout_remote_branch(repo, remote_branch):
    if remote_branch.type == pygit2.enums.ReferenceType.SYMBOLIC:
        raise RuntimeError(f"cannot checkout. {remote_branch.name} is a symbolic ref")

    refname = remote_branch.shorthand

    # Extract branch name (main)
    short_name = refname[refname.index("/") + 1:] # strip off leading "origin/"
    local_refname = f"refs/heads/{short_name}"

    # Create local branch if it doesn't exist
    try:
        local_branch = repo.lookup_reference(local_refname)
    except KeyError:
        commit = remote_branch.peel(pygit2.Commit)
        local_branch = repo.create_branch(short_name, commit)

        # track upstream origin
        local_branch.upstream = remote_branch

    # Checkout working tree
    repo.checkout(local_branch)

def checkout_commit(repo, commit):
    repo.set_head(commit.id)
    repo.checkout_tree(commit, strategy=pygit2.GIT_CHECKOUT_FORCE)

def init_git_repo(repo_url, branch=None):
    repo = None
    checkout_dir = repo_url_to_checkout_path(repo_url)
    checkout_path = os.path.join(os.path.curdir, CHECKOUT_SUBDIR, checkout_dir)
    if os.path.isdir(checkout_path):
        repo = pygit2.Repository(checkout_path)
        remote_urls = [x.url for x in repo.remotes]
        assert(repo_url in remote_urls)
    else:
        os.makedirs(checkout_path, exist_ok=True)
        print(f"Cloning git repository {repo_url} into {checkout_path}...")
        repo = pygit2.clone_repository(repo_url, checkout_path, checkout_branch=branch)
        print("Done")
    
    print(f"Git repository {repo_url} checked out in {checkout_path}")

    # make sure we checkout the required branch
    if branch is not None:
        origin_name = next((r.name for r in repo.remotes), None)
        if origin_name is None:
            raise RuntimeError(f"Could not find a remote orign")
        remote_branch = repo.branches.get(origin_name + "/" + branch)
        checkout_remote_branch(repo, remote_branch)
    return repo

#
# Debug
#

def print_repo_state(repo):
    def print_branch_stats(branch):
        if branch is None:
            return "(None)"

        s = [
                '*' if branch.is_checked_out() else '',
                'H' if branch.is_head() else '',
            ]
        ref = branch.resolve()
        return f"{branch.branch_name}[{''.join(s)}] ({ref.name}) @ {ref.peel().id}"


    print("Local branches:")
    for branch_name in repo.branches.local:
        b = repo.branches.local.get(branch_name)
        ub = b.upstream
        print(f"\t{print_branch_stats(b)} --> {print_branch_stats(ub)}")

    print("Remote branches:")
    for branch_name in repo.branches.remote:
        b = repo.branches.remote.get(branch_name)
        print(f"\t{print_branch_stats(b)}")


