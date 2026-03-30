#!/usr/bin/env python3

from main import *


import pygit2

def get_latest_tag(repo, match_regexes):
    matches = []
    regex = re.compile(match_regexes)
    for ref in repo.references.iterator(pygit2.GIT_REFERENCES_TAGS):
        #tag = repo.lookup_reference(ref).peel(pygit2.Tag)
        commit = ref.peel(pygit2.Commit)
        m = collect_match_group(regex.groupindex, regex.match(ref.name))
        matches.append(m)
        print(ref.name, commit, m)
    #print(matches)


def get_config():
    return {
        "source": {
            "git": {
                "remote": "https://github.com/riscv-software-src/opensbi.git",
            }
        },
        "matcher": {
            "fn": get_latest_tag,
            "args": [
                "^refs/tags/v(?P<major>\\d+).(?P<minor>\\d+)(.(?P<patch>\\d+))?"
            ]
        }
    }


if __name__ == "__main__":
    extract_version(get_config())
