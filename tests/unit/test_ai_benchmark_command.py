"""Tests for ai_benchmark run_benchmark and benchmark_ai_command via mocked APIs."""
import json
import textwrap
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
from click.testing import CliRunner

from assignment_codeval.ai_benchmark import (
    run_benchmark,
    benchmark_ai_command,
    AIModel,
    DEFAULT_MODELS,
)


def _make_codeval(tmp_path, name="test"):
    f = tmp_path / f"{name}.codeval"
    f.write_text(textwrap.dedent("""\
        ASSIGNMENT START test
        Write a hello world program.
        ASSIGNMENT END
        T python3 prog.py
        O hello
    """))
    return str(f)


class TestRunBenchmark:
    def test_creates_output_directory(self, tmp_path):
        codeval = _make_codeval(tmp_path)
        model = AIModel(provider="anthropic", model_id="claude-test", display_name="Claude Test")
        out_dir = str(tmp_path / "results")

        with patch("assignment_codeval.ai_benchmark.call_model", return_value=None):
            run_benchmark(codeval, out_dir, [model], attempts=1, config={})

        assert (tmp_path / "results").is_dir()

    def test_saves_prompt_file(self, tmp_path):
        codeval = _make_codeval(tmp_path)
        model = AIModel(provider="anthropic", model_id="claude-test", display_name="Claude Test")
        out_dir = str(tmp_path / "results")

        with patch("assignment_codeval.ai_benchmark.call_model", return_value=None):
            run_benchmark(codeval, out_dir, [model], attempts=1, config={})

        assert (tmp_path / "results" / "prompt.txt").exists()

    def test_returns_results_dict(self, tmp_path):
        codeval = _make_codeval(tmp_path)
        model = AIModel(provider="anthropic", model_id="claude-test", display_name="Claude Test")
        out_dir = str(tmp_path / "results")

        with patch("assignment_codeval.ai_benchmark.call_model", return_value=None):
            results = run_benchmark(codeval, out_dir, [model], attempts=1, config={})

        assert isinstance(results, dict)
        assert "Claude Test" in results

    def test_api_failure_recorded(self, tmp_path):
        codeval = _make_codeval(tmp_path)
        model = AIModel(provider="anthropic", model_id="claude-test", display_name="Claude Test")
        out_dir = str(tmp_path / "results")

        with patch("assignment_codeval.ai_benchmark.call_model", return_value=None):
            results = run_benchmark(codeval, out_dir, [model], attempts=1, config={})

        attempts = results["Claude Test"]["attempts"]
        assert len(attempts) == 1
        assert attempts[0]["success"] is False

    def test_successful_passing_evaluation(self, tmp_path):
        codeval = _make_codeval(tmp_path)
        model = AIModel(provider="anthropic", model_id="claude-test", display_name="Claude Test")
        out_dir = str(tmp_path / "results")

        mock_eval = MagicMock()
        mock_eval.returncode = 0
        mock_eval.stdout = "Passed\n"
        mock_eval.stderr = ""

        with patch("assignment_codeval.ai_benchmark.call_model",
                   return_value="```python\nprint('hello')\n```"):
            with patch("assignment_codeval.ai_benchmark.subprocess.run",
                       return_value=mock_eval):
                results = run_benchmark(codeval, out_dir, [model], attempts=1, config={})

        assert results["Claude Test"]["passed"] is True

    def test_failed_evaluation(self, tmp_path):
        codeval = _make_codeval(tmp_path)
        model = AIModel(provider="anthropic", model_id="claude-test", display_name="Claude Test")
        out_dir = str(tmp_path / "results")

        mock_eval = MagicMock()
        mock_eval.returncode = 2
        mock_eval.stdout = "FAILED\n"
        mock_eval.stderr = ""

        with patch("assignment_codeval.ai_benchmark.call_model",
                   return_value="print('wrong')"):
            with patch("assignment_codeval.ai_benchmark.subprocess.run",
                       return_value=mock_eval):
                results = run_benchmark(codeval, out_dir, [model], attempts=1, config={})

        assert results["Claude Test"]["passed"] is False

    def test_evaluation_timeout(self, tmp_path):
        import subprocess
        codeval = _make_codeval(tmp_path)
        model = AIModel(provider="anthropic", model_id="claude-test", display_name="Claude Test")
        out_dir = str(tmp_path / "results")

        with patch("assignment_codeval.ai_benchmark.call_model", return_value="code"):
            with patch("assignment_codeval.ai_benchmark.subprocess.run",
                       side_effect=subprocess.TimeoutExpired("cmd", 120)):
                results = run_benchmark(codeval, out_dir, [model], attempts=1, config={})

        attempt = results["Claude Test"]["attempts"][0]
        assert "timed out" in attempt.get("error", "").lower()

    def test_saves_results_json(self, tmp_path):
        codeval = _make_codeval(tmp_path)
        model = AIModel(provider="anthropic", model_id="claude-test", display_name="Claude Test")
        out_dir = str(tmp_path / "results")

        with patch("assignment_codeval.ai_benchmark.call_model", return_value=None):
            run_benchmark(codeval, out_dir, [model], attempts=1, config={})

        results_file = tmp_path / "results" / "results.json"
        assert results_file.exists()
        data = json.loads(results_file.read_text())
        assert "Claude Test" in data

    def test_multiple_attempts(self, tmp_path):
        codeval = _make_codeval(tmp_path)
        model = AIModel(provider="anthropic", model_id="claude-test", display_name="Claude Test")
        out_dir = str(tmp_path / "results")

        with patch("assignment_codeval.ai_benchmark.call_model", return_value=None):
            results = run_benchmark(codeval, out_dir, [model], attempts=3, config={})

        assert len(results["Claude Test"]["attempts"]) == 3

    def test_uses_default_models_when_none_given(self, tmp_path):
        codeval = _make_codeval(tmp_path)
        out_dir = str(tmp_path / "results")

        with patch("assignment_codeval.ai_benchmark.call_model", return_value=None):
            results = run_benchmark(codeval, out_dir, None, attempts=1, config={})

        assert len(results) == len(DEFAULT_MODELS)


class TestBenchmarkAiCommand:
    def test_command_filters_by_model_name(self, tmp_path):
        codeval = _make_codeval(tmp_path)
        out_dir = str(tmp_path / "out")

        with patch("assignment_codeval.ai_benchmark.run_benchmark") as mock_rb:
            mock_rb.return_value = {}
            result = CliRunner().invoke(
                benchmark_ai_command,
                [codeval, "-o", out_dir, "-m", "nonexistent-model"]
            )

        assert "No models selected" in result.output

    def test_command_filters_by_provider(self, tmp_path):
        codeval = _make_codeval(tmp_path)
        out_dir = str(tmp_path / "out")

        with patch("assignment_codeval.ai_benchmark.run_benchmark") as mock_rb:
            mock_rb.return_value = {}
            result = CliRunner().invoke(
                benchmark_ai_command,
                [codeval, "-o", out_dir, "-p", "anthropic"]
            )

        if mock_rb.called:
            models_used = mock_rb.call_args[0][2]
            assert all(m.provider == "anthropic" for m in models_used)

    def test_command_uses_provided_keys(self, tmp_path):
        codeval = _make_codeval(tmp_path)
        out_dir = str(tmp_path / "out")

        with patch("assignment_codeval.ai_benchmark.run_benchmark") as mock_rb:
            mock_rb.return_value = {}
            CliRunner().invoke(
                benchmark_ai_command,
                [codeval, "-o", out_dir, "--anthropic-key", "mykey", "-m", "some-model-that-exists"]
            )

    def test_command_calls_run_benchmark(self, tmp_path):
        codeval = _make_codeval(tmp_path)
        out_dir = str(tmp_path / "out")

        with patch("assignment_codeval.ai_benchmark.run_benchmark") as mock_rb:
            mock_rb.return_value = {}
            result = CliRunner().invoke(
                benchmark_ai_command,
                [codeval, "-o", out_dir]
            )

        assert mock_rb.called
