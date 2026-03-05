#!/usr/bin/env python3
"""Sample program that writes an error message to stderr and exits with code 3."""
import sys

print("something went wrong", file=sys.stderr)
sys.exit(3)
