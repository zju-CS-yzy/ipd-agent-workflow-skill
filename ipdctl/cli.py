"""Compatibility entry point for the IPD lifecycle CLI."""

from .cli_v2 import main

__all__ = ["main"]


if __name__ == "__main__":
    raise SystemExit(main())
