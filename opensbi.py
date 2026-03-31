#!/usr/bin/env python3

from main import *

def get_config():
    return {
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

if __name__ == "__main__":
    extract_version(get_config())
