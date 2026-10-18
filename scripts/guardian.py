#!/usr/bin/env python3
"""
Pharos Threshold Guardian Runner Script
=======================================
Direct entrypoint for executing guardian commands without installation.
"""

import os
import sys

# Ensure repository root is in sys.path
repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from guardian.cli import main

if __name__ == "__main__":
    main()
