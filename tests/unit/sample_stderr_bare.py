#!/usr/bin/env python3
"""Sample program that writes to stderr without a trailing newline."""
import sys

sys.stderr.write("error without newline")
