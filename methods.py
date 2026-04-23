#!/usr/bin/env python3

import re
import os
import logging

#
# Internal versions of the "top level" functions below.
# Operate only on the currently checked-out branch.
#

def __collect_match_group(groupindex, match):
    """
    Collects named capture groups from the regex match `match` into a dict, where each key is given by the
    regex group index in `groupindex`.
    """
    return { k: match.group(v) for k, v in groupindex.items() }

def __match_file(source, file_path, matchers):
    """
    Matches each line of the file `file_path` within the Git repository `repo` by the array of regexs in `matchers`.
    Each match is converted to a dict using `__collect_match_group()` then all matches are flattened into a single dict.

    Returns a tuple containing:
        (current commit object, regex match).
    """
    abspath = os.path.join(source.get_workdir(), file_path)
    matches = []

    commit_ref = source.get_current_commit_ref()

    try:
        with open(abspath, "r") as f:
            for line_num, line in enumerate(f):
                for r in matchers:
                    match = r.search(line)
                    if match:
                        matches.append(__collect_match_group(r.groupindex, match))
    except Exception as ex:
        logging.error(f"Exception while processing file: {file_path}:")
        logging.exception(ex)

    if len(matches) == 0:
        return None

    # Flatten array of dicts into a single dict
    all_matches = {}
    for m in matches:
        all_matches.update(m)
    return (commit_ref, all_matches)

def __latest_matching_tag(source, regex):
    """
    Walks commits in the current Git `repo` in topological order, and finds the most recent commit which
    includes a tag matching the given `regex`.

    Returns a nested tuple containing:
        (tagged commit object, `regex` match)
    """
    result = None

    tag_map = source.get_repo_tags()

    #for commit in repo.walk(repo.head.peel(pygit2.Commit).id, pygit2.GIT_SORT_TOPOLOGICAL):
    #    is_match = False
    #    if commit in tag_map:
    #        commit_tags = tag_map[commit]
    #        for tag in commit_tags:
    #            match = regex.match(tag.name)
    #            if match:
    #                result = (commit, __collect_match_group(regex.groupindex, match))
    #                is_match = True
    #                break
    #    if is_match:
    #        break

    def __tag_matcher(commit):
        if commit in tag_map:
            commit_tags = tag_map[commit]
            for tag in commit_tags:
                match = regex.match(tag.name)
                if match:
                    return (commit, __collect_match_group(regex.groupindex, match))
        return None

    return source.walk_commit_tree_from_head(__tag_matcher)

    return result


#
# "top level" functions intended to be used by project "configurations" to perform extraction of version info from the repository.
#

def latest_matching_tag(repo, match_regex):
    """
    For each remote branch in the `repo`, check it out, then return the most recent commit which contains a tag
    that matches the regex given by `match_regex`.
    """
    # compile the regexes
    compiled_regex = re.compile(match_regex)
    return __latest_matching_tag(repo, compiled_regex)

def match_file(repo, file_path, match_regexes):
    """
    For each remote branch in the `repo`, check it out, then match each regex in the `match_regexes` array against the file
    path specified by `file_path` inside the repo.
    """
    # compile the regexes
    compiled_regexes = [re.compile(x) for x in match_regexes]
    return __match_file(repo, file_path, compiled_regexes)

