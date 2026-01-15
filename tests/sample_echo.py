#!/usr/bin/env python3
"""Sample program that echoes input to stdout."""
import sys

for line in sys.stdin:
    print(line.rstrip('\n'))
