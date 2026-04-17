#!/usr/bin/env python3
"""Sample program that writes to a file for CMP (compare) testing."""
import sys

output_file = sys.argv[1] if len(sys.argv) > 1 else "output.txt"

with open(output_file, "w") as f:
    f.write("line 1\n")
    f.write("line 2\n")
    f.write("line 3\n")

print("File written successfully")
