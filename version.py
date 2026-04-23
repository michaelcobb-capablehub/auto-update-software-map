#!/usr/bin/env python3
import re

class Version():
    def __init__(self):
        pass

class SemanticVersion(Version):
    def __init__(self, major=None, minor=None, patch=None, extra=None):
        Version.__init__(self)
        self._major = int(major) if major else None
        self._minor = int(minor) if minor else None
        self._patch = int(patch) if patch else None
        self._extra = str(extra) if extra else None

    @staticmethod
    def parse(s):
        pattern = r"^(?P<major>\d+)\.(?P<minor>\d+)(\.(?P<patch>\d+))?(-(?P<extra>[\w\-]+))?$"
        m = re.match(pattern, s)
        if m is None:
            raise RuntimeError(f"'{s}': Could not parse")
        major = m.group("major")
        minor = m.group("minor")
        patch = m.group("patch")
        extra = m.group("extra")
        return SemanticVersion(major, minor, patch, extra)

    def __str__(self):
        s = ""
        if self._major is not None:
            s += str(self._major)
        if self._minor is not None:
            s += "." + str(self._minor)
        if self._patch is not None:
            s += "." + str(self._patch)
        if self._extra is not None:
            s += "-" + str(self._extra)
        return s

def make_version(version_type, version_info):
    if version_type == "semantic":
        return SemanticVersion(version_info.get("major"), version_info.get("minor"), version_info.get("patch"), version_info.get("extra"))
    raise RuntimeError(f"Unhandled version_type: {version_type}")
