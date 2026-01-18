#!/usr/bin/env python3
"""Sample program that echoes input to stdout without trailing newline."""
import sys

# Read all input and echo without adding newlines
data = sys.stdin.read()
print(data, end='')
