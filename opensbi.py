#!/usr/bin/env python3

from main import *

def get_config():
    return {
        "name": "opensbi",
        "version_type": "semantic",
        "forks": [
            {
                "name": "upstream",
                "source": {
                    "git": {
                        "remote": "https://github.com/riscv-software-src/opensbi.git",
                        "checkout_dir": "upstream_opensbi"
                    }
                },
                "matcher": {
                    "fn": latest_matching_tag,
                    "args": [
                        "^refs/tags/v(?P<major>\\d+).(?P<minor>\\d+)(.(?P<patch>\\d+))?"
                    ]
                }
            },
            {
                "name": "fork",
                "source": {
                    "git": {
                        "remote": "https://github.com/CHERI-Alliance/opensbi.git",
                        "branch": "codasip-cheri-riscv",
                        "checkout_dir": "opensbi"
                    }
                },
                "matcher": {
                    "fn": match_file,
                    "args": [
                        "include/sbi/sbi_version.h",
                        [
                            "^#define OPENSBI_VERSION_MAJOR (?P<major>\\d+)",
                            "^#define OPENSBI_VERSION_MINOR (?P<minor>\\d+)"
                        ]
                    ]
                }
            }
        ]
    }

if __name__ == "__main__":
    find_repo_version(get_config())
