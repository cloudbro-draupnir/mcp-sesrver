from __future__ import annotations

__all__ = ["__version__", "main"]

# Keep package version in sync with distribution metadata to avoid drift
try:  # Python 3.8+
    from importlib.metadata import PackageNotFoundError, version

    try:
        __version__ = version("draupnir-mcp-server")
    except PackageNotFoundError:
        # Fallback for editable/dev installs where metadata may be absent
        __version__ = "0.0.0"
except Exception:
    # Very defensive fallback
    __version__ = "0.0.0"

from .server import main  # re-export CLI entry
