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
| Submissions tested | _e.g. 30 student submissions_ |
| Assignment type | _e.g. C program with 10 test cases_ |
| Host machine | _e.g. Ubuntu 22.04, 8-core CPU, 16GB RAM_ |
| Docker image | _e.g. codeval:latest_ |
| Run command | `assignment-codeval evaluate-submissions ./codeval ./submissions` |

---

## Results

| Metric | Value |
|--------|-------|
| Total submissions | _e.g. 30_ |
| Total runtime | _e.g. 4m 32s_ |
| Avg time per submission | _e.g. 9.1s_ |
| Peak memory usage | _e.g. 512MB_ |
| Failures / errors | _e.g. 0_ |

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

- _What worked well?_
- _What slowed things down?_
- _Any unexpected failures under load?_

---

## System Limits

| Scenario | Estimated Limit |
|----------|----------------|
| Submissions before memory pressure | _e.g. ~200 with default Docker settings_ |
| Max safe concurrent Docker containers | _e.g. 1 (currently sequential)_ |
| Largest submission handled | _e.g. 50MB zip file_ |

---

## What We Would Optimize

- Parallelize submission evaluation across multiple Docker containers
- Cache Docker image layers to reduce per-submission startup time
- Add a `--jobs N` flag to control concurrency
