#!/usr/bin/env python3
# Python CLI calculator
# Based on cli-calc assignment, adapted for Python.
#
# Usage: pycalc.py number [+|- number]...

import sys


def main():
    if len(sys.argv) < 2:
        print(f"USAGE: {sys.argv[0]} number [+|- number]...")
        sys.exit(1)

    try:
        result = int(sys.argv[1])
    except ValueError:
        print(f"expected an integer. got {sys.argv[1]}")
        sys.exit(2)

    i = 2
    while i < len(sys.argv):
        op = sys.argv[i]
        if op not in ('+', '-'):
            print(f"expected + or -. got {op}")
            sys.exit(2)
        i += 1

        if i >= len(sys.argv):
            print(f"expected an integer. got {op}")
            sys.exit(2)

        try:
            num = int(sys.argv[i])
        except ValueError:
            print(f"expected an integer. got {sys.argv[i]}")
            sys.exit(2)

        if op == '+':
            result += num
        else:
            result -= num
        i += 1

    print(result)


if __name__ == "__main__":
    main()
