#!/usr/bin/env python3
"""
AI Benchmark Module for CodEval

Sends programming assignments to various AI models, collects their solutions,
and evaluates them using the existing CodEval framework.

Supported providers:
- Anthropic (Claude models)
- OpenAI (GPT models)
- Google (Gemini models)
"""

import os
import re
import json
import time
import subprocess
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
from configparser import ConfigParser

import click

from .commons import info, warn, error, debug


@dataclass
class AIModel:
    """Represents an AI model configuration."""
    provider: str  # anthropic, openai, google
    model_id: str
    display_name: str


# Default models to benchmark
DEFAULT_MODELS = [
    # Anthropic models
    AIModel("anthropic", "claude-sonnet-4-20250514", "Claude Sonnet 4"),
    AIModel("anthropic", "claude-opus-4-20250514", "Claude Opus 4"),
    # OpenAI models
    AIModel("openai", "gpt-4o", "GPT-4o"),
    AIModel("openai", "gpt-4o-mini", "GPT-4o Mini"),
    AIModel("openai", "o1", "o1"),
    AIModel("openai", "o3-mini", "o3-mini"),
    # Google models
    AIModel("google", "gemini-2.0-flash", "Gemini 2.0 Flash"),
    AIModel("google", "gemini-1.5-pro-latest", "Gemini 1.5 Pro"),
]


def load_ai_config() -> dict:
    """Load AI API keys from config file."""
    config_path = Path.home() / ".config" / "codeval.ini"
    config = ConfigParser()

    if config_path.exists():
        config.read(config_path)

    return {
        "anthropic_key": config.get("AI", "anthropic_key", fallback=os.environ.get("ANTHROPIC_API_KEY")),
        "openai_key": config.get("AI", "openai_key", fallback=os.environ.get("OPENAI_API_KEY")),
        "google_key": config.get("AI", "google_key", fallback=os.environ.get("GOOGLE_API_KEY")),
    }


def extract_assignment_from_codeval(codeval_path: str) -> tuple[str, str, str]:
    """
    Extract assignment description, compile command, and language from a codeval file.

    Returns:
        (description, compile_command, language)
    """
    with open(codeval_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Extract content between CRT_HW START and CRT_HW END
    match = re.search(r"CRT_HW START \S+\n(.*?)CRT_HW END", content, re.DOTALL)
    if match:
        description = match.group(1).strip()
    else:
        # If no CRT_HW markers, use everything before first tag
        lines = []
        for line in content.split("\n"):
            if re.match(r"^[A-Z]+\s", line):
                break
            lines.append(line)
        description = "\n".join(lines).strip()

    # Extract compile command
    compile_match = re.search(r"^C\s+(.+)$", content, re.MULTILINE)
    compile_cmd = compile_match.group(1) if compile_match else ""

    # Detect language from compile command
    language = "unknown"
    if "gcc" in compile_cmd or "cc " in compile_cmd:
        language = "c"
    elif "g++" in compile_cmd:
        language = "cpp"
    elif "python" in compile_cmd:
        language = "python"
    elif "javac" in compile_cmd:
        language = "java"
    elif "rustc" in compile_cmd or "cargo" in compile_cmd:
        language = "rust"
    elif "go " in compile_cmd:
        language = "go"

    return description, compile_cmd, language


def extract_source_filename(compile_cmd: str) -> str:
    """Extract the source filename from a compile command."""
    # Look for common source file extensions
    match = re.search(r"(\S+\.(c|cpp|cc|py|java|rs|go))", compile_cmd)
    if match:
        return match.group(1)
    return "solution.c"


def build_prompt(description: str, language: str, filename: str) -> str:
    """Build the prompt to send to AI models."""
    lang_hints = {
        "c": "Write the solution in C. Use standard C libraries only.",
        "cpp": "Write the solution in C++. Use standard C++ libraries only.",
        "python": "Write the solution in Python 3.",
        "java": "Write the solution in Java.",
        "rust": "Write the solution in Rust.",
        "go": "Write the solution in Go.",
    }

    hint = lang_hints.get(language, "")

    return f"""You are solving a programming assignment. {hint}

IMPORTANT: Output ONLY the code. No explanations, no markdown code blocks, no comments about the solution. Just the raw source code that can be directly saved to a file and compiled/run.

The solution should be saved as: {filename}

Here is the assignment:

{description}

Remember: Output ONLY the code, nothing else."""


def extract_code_from_response(response: str, language: str) -> str:
    """Extract code from AI response, handling markdown blocks if present."""
    # Try to extract from markdown code block
    patterns = [
        r"```(?:c|cpp|python|java|rust|go)?\n(.*?)```",
        r"```\n(.*?)```",
    ]

    for pattern in patterns:
        match = re.search(pattern, response, re.DOTALL)
        if match:
            return match.group(1).strip()

    # If no code blocks, assume the whole response is code
    # But strip any leading/trailing explanation
    lines = response.strip().split("\n")

    # Remove lines that look like explanations
    code_lines = []
    in_code = False
    for line in lines:
        # Detect start of code
        if not in_code:
            if line.startswith("#include") or line.startswith("import ") or \
               line.startswith("def ") or line.startswith("int ") or \
               line.startswith("void ") or line.startswith("public ") or \
               line.startswith("package ") or line.startswith("use ") or \
               line.startswith("fn ") or line.startswith("func "):
                in_code = True

        if in_code:
            code_lines.append(line)

    if code_lines:
        return "\n".join(code_lines)

    return response.strip()


def call_anthropic(model_id: str, prompt: str, api_key: str) -> Optional[str]:
    """Call Anthropic API."""
    try:
        import anthropic
    except ImportError:
        error("anthropic package not installed. Run: pip install anthropic")
        return None

    try:
        client = anthropic.Anthropic(api_key=api_key)

        # Adjust max_tokens based on model capabilities
        max_tokens = 4096  # Safe default for older models
        if "claude-3-5" in model_id or "claude-sonnet-4" in model_id or "claude-opus-4" in model_id:
            max_tokens = 8192

        message = client.messages.create(
            model=model_id,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}]
        )

        return message.content[0].text
    except Exception as e:
        error(f"Anthropic API error: {e}")
        return None


def call_openai(model_id: str, prompt: str, api_key: str) -> Optional[str]:
    """Call OpenAI API."""
    try:
        import openai
    except ImportError:
        error("openai package not installed. Run: pip install openai")
        return None

    try:
        client = openai.OpenAI(api_key=api_key)

        response = client.chat.completions.create(
            model=model_id,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=8192,
        )

        return response.choices[0].message.content
    except Exception as e:
        error(f"OpenAI API error: {e}")
        return None


def call_google(model_id: str, prompt: str, api_key: str) -> Optional[str]:
    """Call Google Gemini API."""
    try:
        import google.generativeai as genai
    except ImportError:
        error("google-generativeai package not installed. Run: pip install google-generativeai")
        return None

    try:
        genai.configure(api_key=api_key)

        model = genai.GenerativeModel(model_id)
        response = model.generate_content(prompt)

        return response.text
    except Exception as e:
        error(f"Google API error: {e}")
        return None


def call_model(model: AIModel, prompt: str, config: dict) -> Optional[str]:
    """Call the appropriate API based on provider."""
    if model.provider == "anthropic":
        if not config["anthropic_key"]:
            warn(f"No Anthropic API key configured, skipping {model.display_name}")
            return None
        return call_anthropic(model.model_id, prompt, config["anthropic_key"])

    elif model.provider == "openai":
        if not config["openai_key"]:
            warn(f"No OpenAI API key configured, skipping {model.display_name}")
            return None
        return call_openai(model.model_id, prompt, config["openai_key"])

    elif model.provider == "google":
        if not config["google_key"]:
            warn(f"No Google API key configured, skipping {model.display_name}")
            return None
        return call_google(model.model_id, prompt, config["google_key"])

    else:
        error(f"Unknown provider: {model.provider}")
        return None


def run_benchmark(
    codeval_path: str,
    output_dir: str,
    models: Optional[list[AIModel]] = None,
    attempts: int = 1,
    config: Optional[dict] = None,
) -> dict:
    """
    Run benchmark on a codeval assignment with multiple AI models.

    Args:
        codeval_path: Path to the .codeval file
        output_dir: Directory to store solutions and results
        models: List of models to test (defaults to DEFAULT_MODELS)
        attempts: Number of attempts per model
        config: Optional config dict with API keys

    Returns:
        Dictionary with results for each model
    """
    if models is None:
        models = DEFAULT_MODELS

    if config is None:
        config = load_ai_config()

    # Convert to absolute path to avoid issues with relative paths
    codeval_path = str(Path(codeval_path).resolve())

    # Extract assignment info
    description, compile_cmd, language = extract_assignment_from_codeval(codeval_path)
    source_file = extract_source_filename(compile_cmd)

    info(f"Assignment: {Path(codeval_path).stem}")
    info(f"Language: {language}")
    info(f"Source file: {source_file}")

    # Build prompt
    prompt = build_prompt(description, language, source_file)

    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Save prompt for reference
    (output_path / "prompt.txt").write_text(prompt)

    results = {}

    for model in models:
        model_dir = output_path / model.display_name.replace(" ", "_")
        model_dir.mkdir(exist_ok=True)

        model_results = {
            "attempts": [],
            "best_score": 0,
            "passed": False,
        }

        for attempt in range(attempts):
            attempt_dir = model_dir / f"attempt_{attempt + 1}"
            attempt_dir.mkdir(exist_ok=True)

            info(f"\n{'='*60}")
            info(f"Model: {model.display_name} (Attempt {attempt + 1}/{attempts})")
            info(f"{'='*60}")

            # Call the model
            start_time = time.time()
            response = call_model(model, prompt, config)
            elapsed = time.time() - start_time

            if response is None:
                model_results["attempts"].append({
                    "success": False,
                    "error": "API call failed",
                    "time": elapsed,
                })
                continue

            # Save raw response
            (attempt_dir / "raw_response.txt").write_text(response)

            # Extract code
            code = extract_code_from_response(response, language)
            source_path = attempt_dir / source_file
            source_path.write_text(code)

            info(f"Response received in {elapsed:.2f}s")
            info(f"Code saved to {source_path}")

            # Copy codeval file to attempt directory, stripping Z tags (not supported locally)
            import shutil
            try:
                with open(codeval_path, "r", encoding="utf-8") as f:
                    codeval_content = f.read()
                # Remove Z tag lines (zip file downloads only work on Canvas)
                codeval_lines = [line for line in codeval_content.split("\n") if not line.startswith("Z ")]
                (attempt_dir / Path(codeval_path).name).write_text("\n".join(codeval_lines))

                # Copy support files if they exist
                codeval_dir = Path(codeval_path).parent
                support_dir = codeval_dir / "support_files"
                if support_dir.exists():
                    for support_file in support_dir.iterdir():
                        shutil.copy(support_file, attempt_dir / support_file.name)
            except Exception as e:
                error(f"Failed to copy codeval/support files: {e}")
                model_results["attempts"].append({
                    "success": False,
                    "error": f"File copy failed: {e}",
                    "time": elapsed,
                })
                continue

            # Run evaluation using subprocess
            info("Running evaluation...")
            try:
                result = subprocess.run(
                    ["assignment-codeval", "run-evaluation", Path(codeval_path).name],
                    cwd=attempt_dir,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )

                # Save evaluation output
                (attempt_dir / "evaluation_output.txt").write_text(
                    f"=== STDOUT ===\n{result.stdout}\n\n=== STDERR ===\n{result.stderr}"
                )

                eval_passed = result.returncode == 0

                model_results["attempts"].append({
                    "success": True,
                    "passed": eval_passed,
                    "time": elapsed,
                })

                if eval_passed:
                    model_results["passed"] = True
                    info(f"✓ {model.display_name} PASSED")
                else:
                    info(f"✗ {model.display_name} FAILED")
                    # Show brief failure info
                    if "FAILED" in result.stdout:
                        for line in result.stdout.split("\n"):
                            if "FAILED" in line or "Command ran" in line:
                                info(f"  {line.strip()}")

            except subprocess.TimeoutExpired:
                model_results["attempts"].append({
                    "success": False,
                    "error": "Evaluation timed out",
                    "time": elapsed,
                })
                error("Evaluation timed out")
            except Exception as e:
                model_results["attempts"].append({
                    "success": False,
                    "error": str(e),
                    "time": elapsed,
                })
                error(f"Evaluation error: {e}")

        results[model.display_name] = model_results

    # Save results summary
    (output_path / "results.json").write_text(json.dumps(results, indent=2))

    # Print summary
    print("\n" + "="*60)
    print("BENCHMARK RESULTS SUMMARY")
    print("="*60)

    for model_name, result in results.items():
        status = "✓ PASS" if result["passed"] else "✗ FAIL"
        attempts_info = f"{sum(1 for a in result['attempts'] if a.get('passed', False))}/{len(result['attempts'])}"
        print(f"{model_name:30} {status:10} ({attempts_info} attempts passed)")

    return results


@click.command("test-with-ai")
@click.argument("codeval_file", type=click.Path(exists=True))
@click.option("--output-dir", "-o", default="ai_test_results",
              help="Directory to store solutions and results")
@click.option("--attempts", "-n", default=1, type=int,
              help="Number of attempts per model")
@click.option("--models", "-m", multiple=True,
              help="Specific models to test (can be used multiple times)")
@click.option("--providers", "-p", multiple=True,
              type=click.Choice(["anthropic", "openai", "google"]),
              help="Only test models from these providers")
@click.option("--anthropic-key", envvar="ANTHROPIC_API_KEY",
              help="Anthropic API key (or set ANTHROPIC_API_KEY env var)")
@click.option("--openai-key", envvar="OPENAI_API_KEY",
              help="OpenAI API key (or set OPENAI_API_KEY env var)")
@click.option("--google-key", envvar="GOOGLE_API_KEY",
              help="Google API key (or set GOOGLE_API_KEY env var)")
def benchmark_ai_command(codeval_file, output_dir, attempts, models, providers,
                         anthropic_key, openai_key, google_key):
    """
    Test AI models on a programming assignment.

    Sends the assignment to multiple AI models, collects their solutions,
    and evaluates them using the codeval framework.

    API keys can be provided via:
    - Command line options (--anthropic-key, --openai-key, --google-key)
    - Environment variables (ANTHROPIC_API_KEY, OPENAI_API_KEY, GOOGLE_API_KEY)
    - Config file (~/.config/codeval.ini in [AI] section)

    Example:
        assignment-codeval test-with-ai my_assignment.codeval -n 3 -p anthropic
    """
    # Build config from provided keys
    config = load_ai_config()
    if anthropic_key:
        config["anthropic_key"] = anthropic_key
    if openai_key:
        config["openai_key"] = openai_key
    if google_key:
        config["google_key"] = google_key

    # Filter models if specific ones requested
    test_models = DEFAULT_MODELS

    if models:
        test_models = [m for m in DEFAULT_MODELS if m.model_id in models or m.display_name in models]

    if providers:
        test_models = [m for m in test_models if m.provider in providers]

    if not test_models:
        error("No models selected for testing")
        return

    info(f"Testing {len(test_models)} models with {attempts} attempt(s) each")

    run_benchmark(codeval_file, output_dir, test_models, attempts, config)


def get_benchmark_command():
    """Return the Click command for CLI registration."""
    return benchmark_ai_command
