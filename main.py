#!/usr/bin/env python3

import sys
import time
import argparse
import logging

from ruamel.yaml import YAML

from software_versions import *
import methods

DEFAULT_LOGLEVEL = "INFO"

CHECK_ALL_REMOTE_BRANCHES = False

yaml = YAML()
yaml.default_flow_style = False
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

def build_release_metadata_for_branch_commit(src_repo, branch, commit):
    branch_meta = src_repo.get_metadata_for_branch(branch)
    commit_meta = src_repo.get_metadata_for_commit(commit)
    result = {
        "version": str(commit_meta["short_id"]),
        "version_hash": str(commit_meta["id"]),
        "version_branch": str(branch_meta["name"]),
        "version_url": str(commit_meta["url"]),
        "version_date": str(format_datetime_date(commit_meta["datetime"]))
    }
    return result

def build_upstream_release_metadata_for_branch_commit(upstream_repo, upstream_branch, diverge_commit, ver):
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

def update_software_release_version_for_branch(src_repo, fork_branch, applicable_version_methods):
    logging.info(f"Checking version of remote branch '{fork_branch.shorthand}' in {src_repo.get_src_url()}...")
    src_repo.checkout_remote_branch(fork_branch)
    versions = find_repo_version(src_repo, applicable_version_methods)
    if versions is not None:
        commit, ver = versions
        logging.info(f"\t{fork_branch.name}, {commit}, {ver}")
        return versions


def update_software_release_version(src_repo, fork_branch, applicable_version_methods):
    result = None
    src_remote_branches = src_repo.get_repo_remote_branches()
    found_fork_branch = False
    for branch in src_remote_branches:
        versions = update_software_release_version_for_branch(src_repo, branch, applicable_version_methods)
        if versions is None:
            if branch == fork_branch:
                raise RuntimeError(f"No version found for branch '{branch.shorthand}'")
            else:
                logging.warning(f"failed to find version for branch '{branch.shorthand}'")
        if branch == fork_branch:
            result = versions
            found_fork_branch = True

    if not found_fork_branch:
        logging.warning(f"Branch '{fork_branch}' was not found in repository: {src_repo.get_src_url()}")

    return result

def update_software_release_upstream_version(src_repo, upstream_repo, fork_branch, upstream_branch, applicable_upstream_version_methods):
    result = None
    src_repo.checkout_remote_branch(fork_branch)
    upstream_repo.checkout_remote_branch(upstream_branch)
    fork_point = find_repo_fork_upstream_version(upstream_repo, src_repo, applicable_upstream_version_methods)
    if fork_point is not None:
        diverge_commit, commitver = fork_point
        if commitver is not None:
            vercommit, ver = commitver
            logging.info(f"Fork point: {diverge_commit}, Version: {ver}")
            return (diverge_commit, commitver)

    return None

def update_software_release(arch, release, version_methods):
    fork_repo_url = release.get("version_repo")
    current_fork_hash = release.get("version_hash")
    current_fork_date = release.get("version_date")
    current_fork_branch = release.get("version_branch")

    applicable_version_methods = list(filter_applicable_version_methods(version_methods, release.get("applicable_version_methods")))


    # assume all repos are git repos for now
    src_repo = init_source("git", fork_repo_url)
    fork_branch = src_repo.get_origin_branch_ref(current_fork_branch)

    if CHECK_ALL_REMOTE_BRANCHES:
        new_version = update_software_release_version(src_repo, fork_branch, applicable_version_methods)
    else:
        new_version = update_software_release_version_for_branch(src_repo, fork_branch, applicable_version_methods)

    if new_version is not None:
        new_version_commit, new_version_ver = new_version
        new_version_metadata = build_release_metadata_for_branch_commit(src_repo, fork_branch, new_version_commit)

    upstream_repo_url = release.get("upstream_repo")
    current_upstream_hash = release.get("upstream_hash")
    current_upstream_date = release.get("upstream_date")
    current_upstream_branch = release.get("upstream_branch")
    upstream_version = release.get("upstream_version")

    if upstream_repo_url is None:
        new_upstream_version = None
        logging.warning(f"There is no upstream repo set. Upstream version will not be checked")
    else:
        applicable_upstream_version_methods = list(filter_applicable_version_methods(version_methods, release.get("upstream_applicable_version_methods")))

        # assume all repos are git repos for now
        upstream_repo = init_source("git", upstream_repo_url)
        upstream_branch = upstream_repo.get_origin_branch_ref(current_upstream_branch)

        new_upstream_version = update_software_release_upstream_version(src_repo, upstream_repo, fork_branch, upstream_branch, applicable_upstream_version_methods)
        

    logging.debug(f"Arch: {arch}")
    logging.debug(f"\tRelease:")
    logging.debug(f"\t\tRepo: '{fork_repo_url}'")
    logging.debug(f"\t\t\tCommit: {current_fork_hash} ({current_fork_branch}) @ {current_fork_date}")
    logging.debug(f"\t\t\t--> New Commit: {new_version_metadata.get('version_hash')} ({new_version_metadata.get('version_branch')}) @ {new_version_metadata.get('version_date')}")
    if new_upstream_version is not None:
        new_upstream_diverge_commit, new_upstream_commitver = new_upstream_version
        new_upstream_commit, new_upstream_ver = new_upstream_commitver
        new_upstream_version_metadata = build_upstream_release_metadata_for_branch_commit(upstream_repo, upstream_branch, new_upstream_diverge_commit, new_upstream_ver)
        logging.debug(f"\tUpstream:")
        logging.debug(f"\t\tRepo: '{upstream_repo_url}'")
        logging.debug(f"\t\t\tCommit: {current_upstream_hash} ({current_upstream_branch}) @ {current_upstream_date}")
        logging.debug(f"\t\t\t--> New Commit: {new_upstream_version_metadata.get('upstream_hash')} ({new_upstream_version_metadata.get('upstream_branch')}) @ {new_upstream_version_metadata.get('upstream_date')}")
        logging.debug(f"\t\t\tVersion: '{upstream_version}'")
        logging.debug(f"\t\t\t--> New Version: '{new_upstream_version_metadata.get('upstream_version')}'")

    # Update the "release" dict with new version information
    release.update(new_version_metadata)
    if new_upstream_version is not None:
        release.update(new_upstream_version_metadata)

def run_formatter(input_file, output_file):
    """
    do a simple deserialise -> serialise pass (a.k.a format the file with no content changes)
    """
    logging.info(f"formatting '{input_file}'...")
    with open(input_file) as f:
        conf = yaml.load(f)
        if output_file is not None:
            logging.info(f"Writing output to '{output_file}'...")
            with open(output_file, "w") as o:
                yaml.dump(conf, o)


def run_version_updater(input_file, output_file):
    logging.info(f"Updating software versions in '{input_file}'...")
    with open(input_file) as f:
        conf = yaml.load(f)
        software = conf.get("software")

        project_versions = conf.get("project_versions")

        if project_versions is None:
            logging.error(f"{input_file}: Missing required field: 'project_versions', skipping...")
            return 0

        version_methods = list(map(map_method, project_versions.get("version_methods")))

        for s in software:
            arch = s.get("arch")
            releases = s.get("releases")

            for release in releases:
                is_latest = release.get("latest")
                if is_latest:
                    update_software_release(arch, release, version_methods)
                else:
                    logging.info(f"Skipping old release for '{release.get('version')}' ({arch})")

        if output_file is not None:
            logging.info(f"Writing output to '{output_file}'...")
            with open(output_file, "w") as o:
                yaml.dump(conf, o)
        return 0

def main():
    parser = argparse.ArgumentParser(description="Updates the specified software-map project .yaml file with updated version information.")
    parser.add_argument("filename")
    parser.add_argument("-o", "--output", help="Set output file. If omitted, default behaviour is to overwrite the input file.")
    parser.add_argument("-l", "--loglevel", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], default=DEFAULT_LOGLEVEL, help="Set the logging leve.l")
    parser.add_argument("-F", "--format", action="store_true", help="Perform formatting of the input file only - do not actually perform update checks.")
    parser.add_argument("-d", "--dry-run", action="store_true", help="Perform a dry-run. Don't write any output files.")
    args = parser.parse_args()

    input_yaml_file = args.filename
    output_yaml_file = None
    if not args.dry_run:
        output_yaml_file = args.output if args.output is not None else args.filename

    logFormatter = logging.Formatter(fmt="%(levelname)-8s: %(message)s")
    logging.basicConfig(level=getattr(logging, args.loglevel))
    logging.getLogger().handlers[0].setFormatter(logFormatter)

    if args.format:
        return run_formatter(input_yaml_file, output_yaml_file)
    else:
        return run_version_updater(input_yaml_file, output_yaml_file)


if __name__ == "__main__":
    rc = main()
    sys.exit(rc)
