#!/usr/bin/env python3

import sys
import time
import argparse

from ruamel.yaml import YAML

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

def format_datetime_date(datetime):
    return time.strftime("%Y-%m-%d", datetime)

def update_software_release_version(src_repo, fork_branch, applicable_version_methods):
    result = None
    src_remote_branches = src_repo.get_repo_remote_branches()
    for branch in src_remote_branches:
        src_repo.checkout_remote_branch(branch)
        versions = find_repo_version(src_repo, applicable_version_methods)
        if versions is None:
            print(f"Warning: failed to find version of branch {branch.shorthand}")
            if branch == fork_branch:
                raise RuntimeError(f"No version found for branch {branch.shorthand}")
        else:
            commit, ver = versions
            #print("\t", f"{branch.name}, {commit}, {ver}")
            if branch == fork_branch:
                branch_meta = src_repo.get_metadata_for_branch(branch)
                commit_meta = src_repo.get_metadata_for_commit(commit)
                result = {
                    "version": str(commit_meta["short_id"]),
                    "version_hash": str(commit_meta["id"]),
                    "version_branch": str(branch_meta["name"]),
                    "version_url": str(commit_meta["url"]),
                    "version_date": str(format_datetime_date(commit_meta["datetime"]))
                }

    #if not found_current_branch:
    #    print(f"Warning: branch {current_fork_branch} was not found in repository: {fork_repo_url}")
    return result

def update_software_release_upstream_version(src_repo, upstream_repo, fork_branch, upstream_branch, applicable_upstream_version_methods):
    result = None
    src_repo.checkout_remote_branch(fork_branch)
    upstream_repo.checkout_remote_branch(upstream_branch)
    fork_point = find_repo_fork_upstream_version(upstream_repo, src_repo, applicable_upstream_version_methods)
    if fork_point is not None:
        diverge_commit, commitver = fork_point
        if commitver is not None:
            commit, ver = commitver
            #print("Fork point:", diverge_commit, "Version:", ver)
            commit_meta = upstream_repo.get_metadata_for_commit(diverge_commit)
            branch_meta = upstream_repo.get_metadata_for_branch(upstream_branch)
            result = {
                "upstream_version": str(ver),
                "upstream_hash": str(commit_meta["id"]),
                "upstream_branch": str(branch_meta["name"]),
                "upstream_url": str(commit_meta["url"]),
                "upstream_date": str(format_datetime_date(commit_meta["datetime"]))
            }

    return result

def update_software_release(arch, release, version_methods):
    fork_repo_url = release.get("version_repo")
    current_fork_hash = release.get("version_hash")
    current_fork_date = release.get("version_date")
    current_fork_branch = release.get("version_branch")

    applicable_version_methods = list(filter_applicable_version_methods(version_methods, release.get("applicable_version_methods")))


    # assume all repos are git repos for now
    src_repo = init_source("git", fork_repo_url)
    fork_branch = src_repo.get_origin_branch_ref(current_fork_branch)

    new_version = update_software_release_version(src_repo, fork_branch, applicable_version_methods)

    upstream_repo_url = release.get("upstream_repo")
    current_upstream_hash = release.get("upstream_hash")
    current_upstream_date = release.get("upstream_date")
    current_upstream_branch = release.get("upstream_branch")
    upstream_version = release.get("upstream_version")

    applicable_upstream_version_methods = list(filter_applicable_version_methods(version_methods, release.get("upstream_applicable_version_methods")))

    # assume all repos are git repos for now
    upstream_repo = init_source("git", upstream_repo_url)
    upstream_branch = upstream_repo.get_origin_branch_ref(current_upstream_branch)

    new_upstream_version = update_software_release_upstream_version(src_repo, upstream_repo, fork_branch, upstream_branch, applicable_upstream_version_methods)

    print(f"Arch: {arch}")
    print("\t", f"Release:")
    print("\t\t", f"Repo: '{fork_repo_url}'")
    print("\t\t\t", f"Commit: {current_fork_hash} ({current_fork_branch}) @ {current_fork_date}")
    print("\t\t\t", f"--> New Commit: {new_version.get('version_hash')} ({new_version.get('version_branch')}) @ {new_version.get('version_date')}")
    print("\t", f"Upstream:")
    print("\t\t", f"Repo: '{upstream_repo_url}'")
    print("\t\t\t", f"Commit: {current_upstream_hash} ({current_upstream_branch}) @ {current_upstream_date}")
    print("\t\t\t", f"--> New Commit: {new_upstream_version.get('upstream_hash')} ({new_upstream_version.get('upstream_branch')}) @ {new_upstream_version.get('upstream_date')}")
    print("\t\t\t", f"Version: '{upstream_version}'")
    print("\t\t\t", f"--> New Version: '{new_upstream_version.get('upstream_version')}'")

    # Update the "release" dict with new version information
    release.update(new_version)
    release.update(new_upstream_version)


def main():
    parser = argparse.ArgumentParser(
                    description="Updates the software-map .yaml file with updated version information")
    parser.add_argument("filename")
    parser.add_argument("-o", "--output")
    args = parser.parse_args()

    input_yaml_file = args.filename
    output_yaml_file = args.output if args.output is not None else args.filename

    print(f"Checking {input_yaml_file}...")
    with open(input_yaml_file) as f:
        conf = yaml.load(f)
        software = conf.get("software")

        project_versions = conf.get("project_versions")

        version_methods = list(map(map_method, project_versions.get("version_methods")))

        for s in software:
            arch = s.get("arch")
            releases = s.get("releases")

            for release in releases:
                update_software_release(arch, release, version_methods)

        print(f"Writing new yaml to {output_yaml_file}...")
        with open(output_yaml_file, "w") as o:
            new_yaml = yaml.dump(conf, o)


if __name__ == "__main__":
    main()
