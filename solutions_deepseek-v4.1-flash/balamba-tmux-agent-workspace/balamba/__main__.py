"""Allow ``python3 -m balamba`` to behave like ``bin/balamba``."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
