import os
import re
import zipfile

import click


def _read_referenced_file(filename, zip_archives):
    """Read a file referenced by IF/OF/EF from zip archives.

    Args:
        filename: the filename from the tag
        zip_archives: list of opened ZipFile objects

    Returns:
        file contents as string
    """
    for zf in zip_archives:
        try:
            return zf.read(filename).decode("utf-8")
        except KeyError:
            continue

    raise FileNotFoundError(
        f"Referenced file '{filename}' not found in zip archives"
    )


def parse_codeval_tests(codeval_file):
    """Parse a codeval file and extract test cases.

    Returns a list of dicts with keys:
        num, command, input, output, error, exit_code, hidden
    """
    codeval_dir = os.path.dirname(os.path.abspath(codeval_file))

    with open(codeval_file, "r") as f:
        lines = f.readlines()

    # First pass: collect Z tags to open zip archives
    tag_pattern = r"([A-Z_]+) (.*)"
    zip_paths = []
    in_crt_hw = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("CRT_HW") or stripped.startswith("ASSIGNMENT START") or stripped.startswith("ASSIGNMENT END"):
            in_crt_hw = not in_crt_hw
            continue
        if in_crt_hw:
            continue
        m = re.match(tag_pattern, line)
        if m and m.group(1) == "Z":
            zip_paths.append(os.path.join(codeval_dir, m.group(2).strip()))

    # Open zip archives for the duration of parsing
    zip_archives = []
    try:
        for zp in zip_paths:
            if os.path.exists(zp):
                zip_archives.append(zipfile.ZipFile(zp, "r"))

        tests = _parse_codeval_lines(lines, zip_archives)
    finally:
        for zf in zip_archives:
            zf.close()

    return tests


def _parse_codeval_lines(lines, zip_archives):
    """Parse codeval lines into test case dicts."""
    tag_pattern = r"([A-Z_]+) (.*)"
    in_crt_hw_block = False
    tests = []
    current = None
    test_num = 0

    def finalize():
        if current is not None:
            tests.append(current)

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if stripped.startswith("CRT_HW") or stripped.startswith("ASSIGNMENT START") or stripped.startswith("ASSIGNMENT END"):
            in_crt_hw_block = not in_crt_hw_block
            continue

        if in_crt_hw_block:
            continue

        tag_match = re.match(tag_pattern, line)
        if not tag_match:
            continue

        tag = tag_match.group(1)
        args = tag_match.group(2)

        if tag in ("T", "HT"):
            finalize()
            test_num += 1
            current = {
                "num": test_num,
                "command": args,
                "input": "",
                "output": "",
                "error": "",
                "exit_code": -1,
                "hidden": tag == "HT",
            }
        elif tag == "TCMD":
            finalize()
            test_num += 1
            current = {
                "num": test_num,
                "command": args,
                "input": "",
                "output": "",
                "error": "",
                "exit_code": -1,
                "hidden": False,
            }
        elif current is not None:
            if tag == "I":
                current["input"] += args + "\n"
            elif tag == "IB":
                current["input"] += args
            elif tag == "IF":
                current["input"] += _read_referenced_file(
                    args.strip(), zip_archives
                )
            elif tag == "O":
                current["output"] += args + "\n"
            elif tag == "OB":
                current["output"] += args
            elif tag == "OF":
                current["output"] += _read_referenced_file(
                    args.strip(), zip_archives
                )
            elif tag == "E":
                current["error"] += args + "\n"
            elif tag == "EB":
                current["error"] += args
            elif tag == "X":
                current["exit_code"] = int(args.strip())

    finalize()
    return tests


@click.command()
@click.argument("codeval_file", type=click.Path(exists=True))
@click.option("--include-hidden", is_flag=True, help="Include hidden test cases")
@click.option("--output", "-o", default=None, help="Output zip file path")
def export_tests(codeval_file, include_hidden, output):
    """Export test cases from a codeval file into a zip archive.

    Creates a zip with in.X, out.X, err.X files for each test case
    and a TESTS.md summary.
    """
    tests = parse_codeval_tests(codeval_file)

    if output is None:
        basename = os.path.splitext(os.path.basename(codeval_file))[0]
        output = f"{basename}_tests.zip"

    filtered = [t for t in tests if include_hidden or not t["hidden"]]

    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
        tests_md = ""
        for test in filtered:
            num = test["num"]
            zf.writestr(f"in.{num}", test["input"])
            zf.writestr(f"out.{num}", test["output"])
            zf.writestr(f"err.{num}", test["error"])

            tests_md += f"# Test {num}\n"
            tests_md += f"command: `{test['command']}`\n"
            if test["exit_code"] != -1:
                tests_md += f"expected exit code: {test['exit_code']}\n"
            tests_md += "\n"

        zf.writestr("TESTS.md", tests_md)

    click.echo(f"Exported {len(filtered)} test(s) to {output}")
