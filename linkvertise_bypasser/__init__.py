# Package initializer for linkvertise_bypasser
# This file exposes the common API symbols so `from linkvertise_bypasser import bypass, BypassFailedError`
# works whether the implementation lives in:
# - linkvertise_bypasser/linkvertise_bypasser.py
# - linkvertise_bypasser/linkvertise.py
# - a top-level module linkvertise_bypasser.py (next to by.py)
#
# The code below tries a few candidates and re-exports the useful names.

from importlib import import_module
import sys

__all__ = []

# Candidate module names (relative to this package) to look for implementation
_candidates = ("linkvertise_bypasser", "linkvertise", "bypasser", "core")

_impl = None
pkg = __package__ or "linkvertise_bypasser"

# Try to import submodule inside the package (e.g., linkvertise_bypasser/linkvertise_bypasser.py)
for name in _candidates:
    try:
        _impl = import_module(f".{name}", pkg)
        break
    except Exception:
        _impl = None

# If not found inside package, try top-level module (e.g., linkvertise_bypasser.py next to by.py)
if _impl is None:
    for name in ("linkvertise_bypasser", "linkvertise"):
        try:
            _impl = import_module(name)
            break
        except Exception:
            _impl = None

if _impl is None:
    raise ImportError(
        "linkvertise_bypasser package: could not locate implementation module. "
        "Expected one of: "
        + ", ".join([f"package.{n}" for n in _candidates])
        + " or top-level module 'linkvertise_bypasser' / 'linkvertise'. "
        "Please ensure the implementation file exists."
    )

# Names we want to re-export if implemented
_wanted = [
    "bypass",
    "LinkvertiseBypassError",
    "BypassFailedError",
    "InvalidLinkError",
    "InvalidLinkError",
    "parse_link",
    "Post",
    "get_url",
]

for name in _wanted:
    if hasattr(_impl, name):
        globals()[name] = getattr(_impl, name)
        __all__.append(name)

# Also export the implementation module for direct access if needed
_impl_name = getattr(_impl, "__name__", None)
if _impl_name:
    __all__.append("_impl")
    globals()["_impl"] = _impl

# Provide a helpful repr for debugging
def _who_am_i():
    return f"linkvertise_bypasser package re-exporting: {_impl_name}"

__all__.append("_who_am_i")
globals()["_who_am_i"] = _who_am_i