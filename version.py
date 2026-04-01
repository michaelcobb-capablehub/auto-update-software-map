#!/usr/bin/env python3

class Version():
    def __init__(self):
        pass

class SemanticVersion(Version):
    def __init__(self, major=None, minor=None, patch=None):
        Version.__init__(self)
        self._major = int(major) if major else None
        self._minor = int(minor) if minor else None
        self._patch = int(patch) if patch else None

    @staticmethod
    def from_str(s):
        parts = s.split(".")
        if len(parts) < 2 or len(parts) > 3:
            raise RuntimeError(f"{s}: Not a valid semantic version string")
        return SemanticVersion(*parts)

    def __str__(self):
        s = ""
        if self._major is not None:
            s += str(self._major)
        if self._minor is not None:
            s += "." + str(self._minor)
        if self._patch is not None:
            s += "." + str(self._patch)
        return s

def make_version(version_type, version_info):
    if version_type == "semantic":
        return SemanticVersion(version_info.get("major"), version_info.get("minor"), version_info.get("patch"))
    raise RuntimeError(f"Unhandled version_type: {version_type}")
