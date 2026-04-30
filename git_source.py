#!/usr/bin/env python3

import os
import shutil
import urllib.parse
import re
import time
from abc import *
import logging

import pygit2

CHECKOUT_SUBDIR="repos"

GIT_VCS_PROVIDERS = {
    "github.com": "github",
    "morello-project.org": "gitlab"
}

def url_to_safe_path(url, suffix):
    illegal_chars_regex = "[./~]"
    safe_char = "_"

    parts = urllib.parse.urlsplit(url)

    path = parts.path.strip("/")
    path = re.sub(".git$", "", path)
    path = re.sub(illegal_chars_regex, safe_char, path)

    return path + suffix

def make_git_source(url, git_provider, opts=None):
    url_parts = urllib.parse.urlparse(url)
    git_host = url_parts.netloc

    git_provider = GIT_VCS_PROVIDERS.get(git_host)

    if git_provider is None:
        raise RuntimeError(f"Unable to determine Git provider for host: '{git_host}'")

    checkout_branch = None
    if opts is not None:
        checkout_branch = opts.get("branch")

    if git_provider == "github":
        return GitHubGitSource(url, checkout_branch)
    elif git_provider == "gitlab":
        return GitLabGitSource(url, checkout_branch)
    else:
        raise RuntimeError(f"Unknown Git provider: '{git_provider}'")

class Source():
    def __init__(self, src_url):
        self.src_url = src_url

    def get_src_url(self):
        return self.src_url

class GitSource(Source):
    def __init__(self, git_url, checkout_branch=None, *args):
        Source.__init__(self, git_url, *args)
        self.cloned_this_session = False

        self.git_repo = None
        self.checkout_path = os.path.join(os.path.curdir, CHECKOUT_SUBDIR, url_to_safe_path(self.src_url, "_git"))
        if os.path.isdir(self.checkout_path):
            repo = pygit2.Repository(self.checkout_path)
            remote_urls = [x.url for x in repo.remotes]
            assert(self.src_url in remote_urls)

        else:
            os.makedirs(self.checkout_path, exist_ok=True)
            logging.info(f"Cloning git repository {self.src_url} into {self.checkout_path}...")
            repo = pygit2.clone_repository(self.src_url, self.checkout_path, checkout_branch=checkout_branch)
            self.cloned_this_session = True
            logging.info("Done")

        self.git_repo = repo

        logging.info(f"Git repository {self.src_url} checked out in {self.checkout_path}")

        if not self.cloned_this_session:
            # perform "git fetch" on the repo to pull in any latest changes
            self.fetch()
            # merge changes from upstream into all local branches
            for branch_name in self.git_repo.branches.local:
                branch = self.git_repo.branches.get(branch_name)
                self.checkout_local_branch(branch)
                # self.pull_current_branch()

        # make sure we checkout the required branch
        if checkout_branch is not None:
            #origin_name = next((r.name for r in repo.remotes), None)
            #if origin_name is None:
            #    raise RuntimeError(f"Could not find a remote orign")
            #remote_branch = repo.branches.get(origin_name + "/" + branch)
            remote_branch = self.get_origin_branch_ref(checkout_branch)
            self.checkout_remote_branch(remote_branch)

    def get_workdir(self):
        return self.git_repo.workdir

    def commit_in_branch(self, branch, commit):
        """
        Returns True if the Git `commit` is contained within the `branch`. False otherwise.
        """
        branch_commit = branch.peel(pygit2.Commit)
        return self.git_repo.descendant_of(branch_commit.id, commit.id)

    def get_origin_branch_ref(self, branch_name, origin=None):
        remote_origin = None

        if branch_name in self.git_repo.branches.remote:
            return self.git_repo.branches.remote.get(branch_name)

        if origin is not None and origin in self.git_repo.remotes:
            ref_name = f"{remote_origin.name}/{branch_name}"
            if ref_name not in self.git_repo.branches.remote:
                raise RuntimeError(f"ref {ref_name} does not exist in this repository")
            return self.git_repo.branches.get(ref_name)
        else:
            for o in self.git_repo.remotes:
                ref_name = f"{o.name}/{branch_name}"
                if ref_name in self.git_repo.branches.remote:
                    return self.git_repo.branches.get(ref_name)
            raise RuntimeError(f"ref {branch_name} does not exist in any remotes in this repository")

    def get_repo_fork_point(self, fork):
        """
        Returns the first commit from the currently checked-out branch in `fork` that also appears in
        the currently checked-out branch in `upstream`.

        This represents the point at which `fork` divereged from `upstream`.
        """
        # Assert that "fork" is also an instance of GitSource
        assert isinstance(fork, GitSource)

        for commit_frk in fork.git_repo.walk(fork.git_repo.head.target, pygit2.enums.SortMode.TOPOLOGICAL):
            commit_ups = self.git_repo.get(commit_frk.id)
            if commit_ups is not None:
                return commit_ups
        return None

    def get_repo_remote_branches(self):
        branch_refs = map(lambda x: self.git_repo.branches.remote.get(x), self.git_repo.branches.remote)
        non_symbolic_refs = filter(lambda x: x.type != pygit2.enums.ReferenceType.SYMBOLIC, branch_refs)
        return non_symbolic_refs

    def fetch(self, remote_name="origin"):
        remote = self.git_repo.remotes[remote_name]
        logging.info(f"Fetching remote '{remote.name}'")
        remote.fetch()

    def pull_current_branch(self, remote_name="origin"):
        #self.fetch(remote_name)

        if self.git_repo.head_is_detached:
            raise RuntimeError("Not on a branch (detached HEAD)")

        branch = self.git_repo.branches[self.git_repo.head.shorthand]
        upstream = branch.upstream

        if upstream is None:
            raise RuntimeError(f"Branch '{branch.shorthand}' has no upstream")

        local_commit = self.git_repo.revparse_single(branch.name)
        remote_commit = self.git_repo.revparse_single(upstream.name)

        logging.info(f"Pulling '{upstream.shorthand}'...")
        # Check if already up-to-date
        if self.git_repo.descendant_of(local_commit.id, remote_commit.id):
            logging.info("Already up-to-date")
            return

        # Fast-forward?
        if self.git_repo.descendant_of(remote_commit.id, local_commit.id):
            self.git_repo.checkout_tree(remote_commit)
            self.git_repo.set_head(upstream.name)
            logging.info("Fast-forwarded")
            return

        # Otherwise: merge required
        self.git_repo.merge(remote_commit.id)

        if self.git_repo.index.conflicts:
            raise RuntimeError("Merge conflicts detected")

        # Create merge commit
        tree = self.git_repo.index.write_tree()
        self.git_repo.create_commit(
            self.git_repo.head.name,
            self.git_repo.default_signature,
            self.git_repo.default_signature,
            "Merge",
            tree,
            [self.git_repo.head.target, remote_commit.id],
        )

        self.git_repo.state_cleanup()
        logging.info("Merged")
        return

    def checkout_remote_branch(self, remote_branch):
        if remote_branch.type == pygit2.enums.ReferenceType.SYMBOLIC:
            raise RuntimeError(f"cannot checkout. {remote_branch.name} is a symbolic ref")

        refname = remote_branch.shorthand

        # Extract branch name
        short_name = refname[refname.index("/") + 1:] # strip off leading "origin/"
        local_refname = f"refs/heads/{short_name}"

        # Create local branch if it doesn't exist
        try:
            local_branch = self.git_repo.lookup_reference(local_refname)
        except KeyError:
            commit = remote_branch.peel(pygit2.Commit)
            local_branch = self.git_repo.create_branch(short_name, commit)

            # track upstream origin
            local_branch.upstream = remote_branch

        # Checkout working tree
        self.checkout_local_branch(local_branch)

    def checkout_local_branch(self, local_branch):
        # Checkout working tree
        self.git_repo.checkout(local_branch, strategy=pygit2.enums.CheckoutStrategy.FORCE | pygit2.enums.CheckoutStrategy.RECREATE_MISSING)
        logging.debug(f"Checking out branch '{local_branch.shorthand}'")

    def checkout_commit(self, commit):
        self.git_repo.set_head(commit.id)
        self.git_repo.checkout_tree(commit, strategy=pygit2.enums.CheckoutStrategy.FORCE | pygit2.enums.CheckoutStrategy.RECREATE_MISSING)
        logging.debug(f"Checked out commit '{commit.id}' (detached HEAD)")

    def get_current_commit_ref(self):
        return self.git_repo.head.peel(pygit2.Commit)

    def get_repo_tags(self):
        tag_map = {}
        for ref in self.git_repo.references.iterator(pygit2.GIT_REFERENCES_TAGS):
            commit = ref.peel(pygit2.Commit)
            tag_map.setdefault(commit, []).append(ref)
        return tag_map

    def walk_commit_tree_from_head(self, callback):
        for commit in self.git_repo.walk(self.git_repo.head.peel(pygit2.Commit).id, pygit2.GIT_SORT_TOPOLOGICAL):
            result = callback(commit)
            if result is not None:
                return result

    def get_metadata_for_branch(self, branch):
        return {
            "name": branch.shorthand
        }

    def get_metadata_for_commit(self, commit):
        commit_datetime = time.gmtime(commit.commit_time)
        return {
            "short_id": commit.short_id,
            "id": commit.id,
            "url": self.get_url_for_commit(commit),
            "datetime": commit_datetime
        }

    @abstractmethod
    def get_url_for_commit(self, commit):
        raise NotImplementedError("Abstract method")

class GitHubGitSource(GitSource):
    def __init__(self, git_url, checkout_branch, *args):
        GitSource.__init__(self, git_url, checkout_branch, *args)

    def get_url_for_commit(self, commit):
        parts = urllib.parse.urlparse(self.src_url)
        path_strip = re.sub(".git$", "", parts.path)
        commit_path = f"{path_strip}/commit/{commit.id}"
        return urllib.parse.urlunparse((parts.scheme, parts.netloc, commit_path, parts.params, parts.query, parts.fragment))

class GitLabGitSource(GitSource):
    def __init__(self, git_url, checkout_branch, *args):
        GitSource.__init__(self, git_url, checkout_branch, *args)

    def get_url_for_commit(self, commit):
        raise NotImplementedError()

