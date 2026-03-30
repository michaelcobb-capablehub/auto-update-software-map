#!/usr/bin/env python3

import os
import shutil

import pygit2

DEBUG = True
#DEBUG = False

def empty_dir(path):
    if len(path) == 0 or path == ".":
        raise RuntimeError(f"Refusing to touch path: {path}")

    if os.path.isfile(path):
        raise RuntimeError(f"{path} is a file")

    if os.path.isdir(path):
        shutil.rmtree(path)
    os.mkdir(path)

def init_git_repo(repo_url, path, branch=None):
    if not DEBUG or not os.path.isdir(path):
        empty_dir(path)
        print(f"Cloning git repository {repo_url} into {path}...")
        pygit2.clone_repository(repo_url, path, checkout_branch=branch)
        print("Done")
    repo = pygit2.Repository(path)
    if DEBUG:
        remote_urls = [x.url for x in repo.remotes]
        assert(repo_url in remote_urls)
    # make sure we checkout the required branch
    if branch is not None:
        origin_name = next((r.name for r in repo.remotes), None)
        if origin_name is None:
            raise RuntimeError(f"Error: Could not find a remote orign")
        b = repo.branches[origin_name + '/' + branch]
        if b is None:
            raise RuntimeError(f"Error: Branch {branch} does not exist")
        ref = repo.lookup_reference(b.name)
        repo.checkout(ref)
    return repo

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


