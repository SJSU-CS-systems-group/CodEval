---
name: test
description: Run the pytest test suite
argument-hint: "[test-pattern]"
---

# Run Tests

Run the project's test suite using pytest.

## Default behavior (no arguments)

Run all tests:
```bash
pytest tests/ -v
```

## With arguments

If `$ARGUMENTS` is provided, use it as a test filter:
```bash
pytest tests/ -v -k "$ARGUMENTS"
```

Examples:
- `/test` - run all tests
- `/test codeval` - run tests matching "codeval"
- `/test "basic or compile"` - run tests matching "basic" or "compile"

## On failure

If tests fail, analyze the output and suggest fixes. Do not automatically modify code unless the user asks.
