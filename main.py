#!/usr/bin/env python3

import os
import re
#import shutil

from git_source import *

DEBUG = True
#DEBUG = False

def collect_match_group(groupindex, match):
    return { k: match.group(v) for k, v in groupindex.items() }

def collect_match_groups(regex_matches):
    for grp, match in regex_matches:
        g = match.groups()
        print(grp, g)

def __match_file(dir, file_path, matchers):
    path = os.path.join(dir, file_path)
    matches = []

    # compile the regexes
    regexes = [re.compile(x) for x in matchers]

    with open(path, "r") as f:
        for line_num, line in enumerate(f):
            for r in regexes:
                match = r.search(line)
                if match:
                    matches.append(collect_match_group(r.groupindex, match))
    # Flatten array of dicts into a single dict
    all_matches = {}
    for m in matches:
        all_matches.update(m)
    return all_matches

def from_file(dir, file_path):
    path = os.path.join(dir, file_path)
    v = None
    with open(path, "r") as f:
        for line in f:
            v = line
            break
    return v

def match_file(repo, file_path, matcher):
    repo_path = repo.workdir # Assuume `repo` is an instance of pygit2.Repository
    return __match_file(repo_path, file_path, matcher)

###############################################################################


def init_source(conf_source, repo_path):
    if "git" in conf_source:
        git_source = conf_source["git"]
        repo = init_git_repo(git_source["remote"], repo_path, git_source["branch"])
        return repo
    else:
        raise RuntimeError(f"Error: No valid sources in: {list(conf_source.keys())}")

def init_matcher(conf_matcher, repo):
    def call_matcher():
        return conf_matcher["fn"](repo, *conf_matcher["args"])

    return call_matcher

CLONE_DIR = "test_git"

def extract_version(conf):
    conf_source = conf["source"]
    repo = init_source(conf_source, CLONE_DIR)
    print("Source:", repo)

    conf_matcher = conf["matcher"]
    m = init_matcher(conf_matcher, repo)
    print("Matcher:", m)
    print(m())

