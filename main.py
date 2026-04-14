#!/usr/bin/env python3

import sys
import time

from ruamel.yaml import YAML
import urllib as urllib

from software_versions import *
import methods

yaml = YAML()
yaml.default_flow_style=False
yaml.width = sys.maxsize
yaml.preserve_quotes = True

def lookup_method_fn(method_name):
    return getattr(methods, method_name)

def map_method(method):
    # We need a copy of the original "method" dict, so that we can add new keys ("fn") without modifying the original, since we will eventually reserialise it back to Yaml
    method_copy = method.copy()
    method_copy["fn"] = lookup_method_fn(method["method"])
    return method_copy

def filter_applicable_version_methods(all_methods, applicable):
    return filter(lambda x: x["method"] in applicable if applicable is not None else True, all_methods)

def make_url_for_commit(repo_url, commit):
    parts = urllib.parse.urlparse(repo_url)
    if parts.netloc == "github.com":
        path_strip = re.sub(".git$", "", parts.path)
        commit_path = f"{path_strip}/commit/{commit.id}"
    else:
        raise RuntimeError(f"Unknown git host: {parts.netloc}")
    return urllib.parse.urlunparse((parts.scheme, parts.netloc, commit_path, parts.params, parts.query, parts.fragment))

def update_software_release_version(src_repo, fork_branch, applicable_version_methods):
    result = None
    src_remote_branches = get_repo_remote_branches(src_repo.get("repo"))
    for branch in src_remote_branches:
        checkout_remote_branch(src_repo.get("repo"), branch)
        versions = find_repo_version(src_repo, applicable_version_methods)
        if versions is None:
            print(f"Warning: failed to find version of branch {branch.shorthand}")
            if branch == fork_branch:
                raise RuntimeError(f"No version found for branch {branch.shorthand}")
        else:
            commit, ver = versions
            #print("\t", f"{branch.name}, {commit}, {ver}")
            if branch == fork_branch:
                commit_datetime = time.gmtime(commit.commit_time)
                result = {
                    "version": str(commit.short_id),
                    "version_hash": str(commit.id),
                    "version_branch": str(branch.shorthand),
                    "version_url": str(make_url_for_commit(src_repo.get("remote"), commit)),
                    "version_date": str(time.strftime("%Y-%m-%d", commit_datetime))
                }

    #if not found_current_branch:
    #    print(f"Warning: branch {current_fork_branch} was not found in repository: {fork_repo_url}")
    return result

def update_software_release_upstream_version(src_repo, upstream_repo, fork_branch, upstream_branch, applicable_upstream_version_methods):
    result = None
    checkout_remote_branch(src_repo.get("repo"), fork_branch)
    checkout_remote_branch(upstream_repo.get("repo"), upstream_branch)
    fork_point = find_repo_fork_upstream_version(upstream_repo, src_repo, applicable_upstream_version_methods)
    if fork_point is not None:
        diverge_commit, commitver = fork_point
        if commitver is not None:
            commit, ver = commitver
            #print("Fork point:", diverge_commit, "Version:", ver)
            commit_datetime = time.gmtime(diverge_commit.commit_time)
            result = {
                "upstream_version": str(ver),
                "upstream_hash": str(diverge_commit.id),
                "upstream_branch": str(upstream_branch.shorthand),
                "upstream_url": str(make_url_for_commit(upstream_repo.get("remote"), diverge_commit)),
                "upstream_date": str(time.strftime("%Y-%m-%d", commit_datetime))
            }

    return result

def update_software_release(arch, release, version_methods):
    fork_repo_url = release.get("version_repo")
    current_fork_hash = release.get("version_hash")
    current_fork_date = release.get("version_date")
    current_fork_branch = release.get("version_branch")
    #current_fork_version = release.get("version")

    applicable_version_methods = list(filter_applicable_version_methods(version_methods, release.get("applicable_version_methods")))


    # assume all repos are git repos for now
    src_conf = { "git": { "remote": fork_repo_url } }
    src_repo = init_source(src_conf)
    fork_branch = get_origin_branch_ref(src_repo.get("repo"), current_fork_branch)

    new_version = update_software_release_version(src_repo, fork_branch, applicable_version_methods)

    upstream_repo_url = release.get("upstream_repo")
    current_upstream_hash = release.get("upstream_hash")
    current_upstream_date = release.get("upstream_date")
    current_upstream_branch = release.get("upstream_branch")
    upstream_version = release.get("upstream_version")

    applicable_upstream_version_methods = list(filter_applicable_version_methods(version_methods, release.get("upstream_applicable_version_methods")))


    upstream_src_conf = { "git": { "remote": upstream_repo_url } }
    upstream_repo = init_source(upstream_src_conf)
    upstream_branch = get_origin_branch_ref(upstream_repo.get("repo"), current_upstream_branch)

    new_upstream_version = update_software_release_upstream_version(src_repo, upstream_repo, fork_branch, upstream_branch, applicable_upstream_version_methods)

    print(f"Arch: {arch}")
    print("\t", f"Release:")
    print("\t\t", f"Repo: '{fork_repo_url}'")
    print("\t\t\t", f"Commit: {current_fork_hash} ({current_fork_branch}) @ {current_fork_date}")
    print("\t\t\t", f"--> New Commit: {new_version.get("version_hash")} ({new_version.get("version_branch")}) @ {new_version.get("version_date")}")
    print("\t", f"Upstream:")
    print("\t\t", f"Repo: '{upstream_repo_url}'")
    print("\t\t\t", f"Branch: '{current_upstream_branch}' Commit: {current_upstream_hash}")
    print("\t\t\t", f"Commit: {current_upstream_hash} ({current_upstream_branch}) @ {current_upstream_date}")
    print("\t\t\t", f"--> New Commit: {new_upstream_version.get("upstream_hash")} ({new_upstream_version.get("upstream_branch")}) @ {new_upstream_version.get("upstream_date")}")
    print("\t\t\t", f"Version: '{upstream_version}'")
    print("\t\t\t", f"--> New Version: '{new_upstream_version.get("upstream_version")}'")

    #print("New version:", new_version)
    #print("New upstream version:", new_upstream_version)

    # Update the "release" dict with new version information
    release.update(new_version)
    release.update(new_upstream_version)


def main():
    project_yaml_file = sys.argv[1]

    with open(project_yaml_file) as f:
        conf = yaml.load(f)
        software = conf.get("software")

        project_versions = conf.get("project_versions")

        version_methods = list(map(map_method, project_versions.get("version_methods")))

        for s in software:
            arch = s.get("arch")
            releases = s.get("releases")

            for release in releases:
                update_software_release(arch, release, version_methods)

        out_file = os.path.basename(project_yaml_file)
        with open(out_file + ".new", "w") as o:
            new_yaml = yaml.dump(conf, o)


if __name__ == "__main__":
    main()
