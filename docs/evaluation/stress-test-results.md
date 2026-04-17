# Stress Test Results

## Overview

CodEval is a CLI batch-processing tool, not a web server. "Stress testing" here means
evaluating how it performs when processing a large number of student submissions
back-to-back — measuring throughput, memory usage, and where bottlenecks occur.

---

## Test Configuration

| Parameter | Value |
|-----------|-------|
| Tool | Manual timing + `time` command |
| Submissions tested | 35 student submissions |
| Assignment type | Python program with 8 test cases (I/O + exit code checks) |
| Host machine | Ubuntu 22.04, 4-core CPU, 8GB RAM |
| Docker image | codeval:latest |
| Run command | `assignment-codeval evaluate-submissions ./codeval ./submissions` |

---

## Results

| Metric | Value |
|--------|-------|
| Total submissions | 35 |
| Total runtime | 5m 21s |
| Avg time per submission | 9.2s |
| Peak memory usage | 310MB |
| Failures / errors | 2 (compile failures due to student syntax errors) |

---

## Bottlenecks

- **Docker startup overhead**: Each submission spawns a new Docker container, which
  adds ~2–3s of fixed overhead per submission regardless of test complexity.
- **Sequential processing**: Submissions are evaluated one at a time. A large class
  (100+ students) will take proportionally longer with no parallelism.
- **Compile timeouts**: Submissions that fail to compile still wait for the full
  compile timeout before moving on.

---

## Observations

- Processing 35 submissions completed reliably with no crashes or hangs.
- Docker startup time dominated per-submission cost (~2.5s out of ~9.2s avg).
- The 2 failed submissions were due to student code errors, not tool failures; CodEval
  handled them gracefully and continued to the next submission.
- Memory usage stayed flat across all 35 submissions — no accumulation or leak detected.

---

## System Limits

| Scenario | Estimated Limit |
|----------|----------------|
| Submissions before memory pressure | ~180 with default Docker settings |
| Max safe concurrent Docker containers | 1 (currently sequential) |
| Largest submission handled | 14MB zip file |

---

## What We Would Optimize

- Parallelize submission evaluation across multiple Docker containers
- Cache Docker image layers to reduce per-submission startup time
- Add a `--jobs N` flag to control concurrency
