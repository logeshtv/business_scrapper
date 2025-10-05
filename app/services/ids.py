from __future__ import annotations

from cuid2.generator import cuid_wrapper

_cuid = cuid_wrapper()


def new_id() -> str:
    """Return a cuid2-compatible identifier string."""
    return _cuid()
