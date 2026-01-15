#!/usr/bin/env python3
"""Sample program that outputs hello to stdout and bye to stderr."""
import sys

print("hello")
print("bye", file=sys.stderr)
