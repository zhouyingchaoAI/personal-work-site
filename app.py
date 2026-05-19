#!/usr/bin/env python3
"""Application entry point.

The platform backend is split under ``backend/`` by feature area. ``backend.runtime``
loads those modules with the legacy shared namespace so the current behavior stays
stable while the codebase is easier to navigate and extend.
"""
from backend.runtime import main


if __name__ == "__main__":
    main()
