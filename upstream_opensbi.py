#!/usr/bin/env python3

from main import *

def get_config():
    return {
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
    }


if __name__ == "__main__":
    extract_version(get_config())
