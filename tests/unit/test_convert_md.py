"""Unit tests for convertMD2Html.py."""
from assignment_codeval.convertMD2Html import mdToHtml


def test_exmpls_substitution_handles_backslashes_in_samples(tmp_path):
    """A backslash sequence in sample output (e.g. \\d) must not break EXMPLS substitution.

    The sample text is spliced into the description in place of the EXMPLS macro;
    if it is treated as a regex replacement string, "\\d" raises re.error.
    """
    spec = tmp_path / "hw.codeval"
    spec.write_text(
        "CRT_HW START Title\n"
        "Here are some examples:\n"
        "EXMPLS 1\n"
        "CRT_HW END\n"
        "T echo hi\n"
        "O \\d+ matches digits\n"
    )
    # Must not raise re.error.
    name, html = mdToHtml(str(spec))
    assert name == "Title"
    assert "EXMPLS" not in html  # the macro was replaced
    assert "matches digits" in html


def test_exmpls_count_parsing_ignores_prose(tmp_path):
    """A description sentence containing 'EXMPLS ' must not crash count parsing."""
    spec = tmp_path / "hw.codeval"
    spec.write_text(
        "CRT_HW START Title\n"
        "The grader uses EXMPLS to show examples.\n"
        "EXMPLS 1\n"
        "CRT_HW END\n"
        "T echo hi\n"
        "O hi\n"
    )
    name, html = mdToHtml(str(spec))
    assert name == "Title"
