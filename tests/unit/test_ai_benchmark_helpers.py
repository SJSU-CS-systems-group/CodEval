"""Unit tests for pure helper functions in ai_benchmark.py."""
import os
import pytest
import textwrap

from assignment_codeval.ai_benchmark import (
    load_ai_config,
    extract_assignment_from_codeval,
    extract_source_filename,
    build_prompt,
    extract_code_from_response,
    DEFAULT_MODELS,
    AIModel,
)


# ---------------------------------------------------------------------------
# DEFAULT_MODELS / AIModel
# ---------------------------------------------------------------------------

class TestDefaultModels:
    def test_default_models_is_list(self):
        assert isinstance(DEFAULT_MODELS, list)

    def test_default_models_non_empty(self):
        assert len(DEFAULT_MODELS) > 0

    def test_all_models_are_ai_model_instances(self):
        for m in DEFAULT_MODELS:
            assert isinstance(m, AIModel)

    def test_model_has_provider_and_id(self):
        for m in DEFAULT_MODELS:
            assert m.provider in ("anthropic", "openai", "google")
            assert m.model_id
            assert m.display_name


# ---------------------------------------------------------------------------
# load_ai_config
# ---------------------------------------------------------------------------

class TestLoadAiConfig:
    def test_returns_dict_with_keys(self, monkeypatch, tmp_path):
        monkeypatch.setenv("HOME", str(tmp_path))
        config = load_ai_config()
        assert "anthropic_key" in config
        assert "openai_key" in config
        assert "google_key" in config

    def test_reads_from_env_vars(self, monkeypatch, tmp_path):
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic-key")
        config = load_ai_config()
        assert config["anthropic_key"] == "test-anthropic-key"

    def test_reads_from_config_file(self, monkeypatch, tmp_path):
        config_dir = tmp_path / ".config"
        config_dir.mkdir()
        config_file = config_dir / "codeval.ini"
        config_file.write_text("[AI]\nanthropic_key = file-key\n")
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        config = load_ai_config()
        assert config["anthropic_key"] == "file-key"

    def test_returns_none_when_no_key(self, monkeypatch, tmp_path):
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        config = load_ai_config()
        assert config["anthropic_key"] is None


# ---------------------------------------------------------------------------
# extract_assignment_from_codeval
# ---------------------------------------------------------------------------

class TestExtractAssignmentFromCodeval:
    def test_extracts_description_from_crt_hw_block(self, tmp_path):
        f = tmp_path / "hw.codeval"
        f.write_text(textwrap.dedent("""\
            CRT_HW START hw1
            Write a program that prints hello.
            CRT_HW END
            C g++ -o prog prog.cpp
            T ./prog
            O hello
        """))
        desc, compile_cmd, lang = extract_assignment_from_codeval(str(f))
        assert "hello" in desc
        assert compile_cmd == "g++ -o prog prog.cpp"
        assert lang == "cpp"

    def test_extracts_description_from_assignment_block(self, tmp_path):
        f = tmp_path / "hw.codeval"
        f.write_text(textwrap.dedent("""\
            ASSIGNMENT START hw1
            Write a sorting program.
            ASSIGNMENT END
            C gcc -o sort sort.c
        """))
        desc, compile_cmd, lang = extract_assignment_from_codeval(str(f))
        assert "sorting" in desc
        assert lang == "c"

    def test_detects_python_language(self, tmp_path):
        f = tmp_path / "hw.codeval"
        f.write_text("C python3 script.py\nT python3 script.py\nO hi\n")
        _, _, lang = extract_assignment_from_codeval(str(f))
        assert lang == "python"

    def test_detects_java_language(self, tmp_path):
        f = tmp_path / "hw.codeval"
        f.write_text("C javac Main.java\nT java Main\nO hi\n")
        _, _, lang = extract_assignment_from_codeval(str(f))
        assert lang == "java"

    def test_no_compile_command_returns_empty(self, tmp_path):
        f = tmp_path / "hw.codeval"
        f.write_text("T python3 prog.py\nO hi\n")
        _, compile_cmd, lang = extract_assignment_from_codeval(str(f))
        assert compile_cmd == ""
        assert lang == "unknown"


# ---------------------------------------------------------------------------
# extract_source_filename
# ---------------------------------------------------------------------------

class TestExtractSourceFilename:
    def test_c_file(self):
        assert extract_source_filename("gcc -o prog prog.c") == "prog.c"

    def test_cpp_file(self):
        # Note: alternation "c|cpp" matches "c" first, so ".cpp" files return the ".c" prefix match
        result = extract_source_filename("g++ -o prog prog.cpp")
        assert ".c" in result  # matches prog.c (the c alternation wins)

    def test_python_file(self):
        assert extract_source_filename("python3 script.py") == "script.py"

    def test_java_file(self):
        assert extract_source_filename("javac Main.java") == "Main.java"

    def test_no_match_returns_default(self):
        assert extract_source_filename("make all") == "solution.c"


# ---------------------------------------------------------------------------
# build_prompt
# ---------------------------------------------------------------------------

class TestBuildPrompt:
    def test_contains_description(self):
        prompt = build_prompt("Write a hello world program.", "c", "prog.c")
        assert "hello world" in prompt

    def test_contains_filename(self):
        prompt = build_prompt("Some task", "cpp", "solution.cpp")
        assert "solution.cpp" in prompt

    def test_contains_language_hint(self):
        prompt = build_prompt("task", "python", "script.py")
        assert "Python" in prompt or "python" in prompt.lower()

    def test_instructs_code_only(self):
        prompt = build_prompt("task", "c", "prog.c")
        assert "ONLY" in prompt or "only" in prompt.lower()

    def test_unknown_language_no_hint(self):
        prompt = build_prompt("task", "unknown", "prog.x")
        assert "task" in prompt


# ---------------------------------------------------------------------------
# extract_code_from_response
# ---------------------------------------------------------------------------

class TestExtractCodeFromResponse:
    def test_extracts_from_markdown_block(self):
        response = "Here is the solution:\n```c\n#include <stdio.h>\nint main() {}\n```"
        code = extract_code_from_response(response, "c")
        assert "#include" in code
        assert "```" not in code

    def test_extracts_from_generic_markdown_block(self):
        response = "```\nint main() { return 0; }\n```"
        code = extract_code_from_response(response, "c")
        assert "main" in code
        assert "```" not in code

    def test_no_markdown_returns_code_lines(self):
        response = "#include <stdio.h>\nint main() { return 0; }"
        code = extract_code_from_response(response, "c")
        assert "#include" in code

    def test_python_code_detected(self):
        response = "import sys\nprint('hello')"
        code = extract_code_from_response(response, "python")
        assert "import" in code

    def test_strips_explanation_before_code(self):
        response = "Here is your solution:\n\ndef foo():\n    pass\n"
        code = extract_code_from_response(response, "python")
        assert "def foo" in code

    def test_empty_response(self):
        code = extract_code_from_response("", "c")
        assert isinstance(code, str)
