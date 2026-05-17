# AI Evaluation Pipeline

A replayable, staged evaluation pipeline for an AI-powered task runner. It reads task examples, scores quality, checks safety, generates retry instructions, and produces a final report — all with strict stage separation and deterministic verdict logic.

---

## Table of Contents

- [Overview](#overview)
- [Project Structure](#project-structure)
- [Setup](#setup)
- [Running the Pipeline](#running-the-pipeline)
- [Pipeline Stages](#pipeline-stages)
- [Output Artifacts](#output-artifacts)
- [Configuration](#configuration)
- [Technical Constraints](#technical-constraints)
- [Adding Policy Files](#adding-policy-files)
- [Validation Checks](#validation-checks)

---

## Overview

The pipeline takes a `task_suite.json` file containing AI task examples and runs them through a multi-stage evaluation:

1. **Parse** — deterministic, no LLM
2. **Quality Evaluation** — per-task LLM call, scores instruction-following and task success
3. **Safety Review** — per-task LLM call, detects violations and guardrail breaches
4. **Retry Generation** — per-task LLM call, produces improved prompts (never sees scores)
5. **Final Report** — deterministic verdict computation, no LLM
6. **Consistency Check** — single LLM call across all quality results
7. **Validation** — code-level checks on all artifacts

Every run regenerates all artifacts from scratch. Static precomputed outputs are not accepted.

---

## Project Structure

```
Deriv Test/
│
├── task_suite.json              # Input: task examples to evaluate
├── settings.py                  # Central config: model, provider, agent factory
├── run.py                       # CLI entry point
├── validate.py                  # Standalone artifact validator (10 checks)
│
├── policies/                    # Optional policy files (.txt / .md)
│   └── .gitkeep                 # Drop policy files here; auto-injected into Stage 2
│
├── pipeline/
│   ├── state.py                 # Stage enum + PipelineState (enforces linear flow)
│   ├── llm_logger.py            # Appends to llm_calls.jsonl; truncates on each run
│   ├── pipeline.py              # Orchestrator — drives all 9 stages in order
│   │
│   ├── models/                  # Pydantic models (one file per domain)
│   │   ├── task.py              # Task, ParsedTask, TaskSuite
│   │   ├── quality.py           # QualityEvalResult, ConstraintResult
│   │   ├── safety.py            # SafetyReviewResult, Violation
│   │   ├── retry.py             # RetryInstruction
│   │   ├── report.py            # TaskSummary
│   │   ├── consistency.py       # ConsistencyIssue, ConsistencyCheckResult
│   │   └── llm_log.py           # LLMCallLog
│   │
│   ├── prompts/                 # Prompt builders (one file per stage)
│   │   ├── quality_prompt.py    # Stage 1 prompt
│   │   ├── safety_prompt.py     # Stage 2 prompt (+ policy injection)
│   │   ├── retry_prompt.py      # Stage 3 prompt (Task-only, never sees scores)
│   │   └── consistency_prompt.py# Consistency check prompt
│   │
│   └── stages/                  # Stage implementations
│       ├── stage_00_parse.py    # Deterministic parsing, no LLM
│       ├── stage_01_quality.py  # LLM — quality evaluation
│       ├── stage_02_safety.py   # LLM — safety review
│       ├── stage_03_retry.py    # LLM — retry instructions (scores excluded)
│       ├── stage_04_report.py   # Deterministic verdicts + final_report.md
│       └── stage_05_consistency.py # Single cross-task LLM call
│
└── [Generated artifacts — recreated on every run]
    ├── parsed_tasks/tasks.json
    ├── quality_eval.json
    ├── safety_review.json
    ├── retry_instructions.json
    ├── summary.json
    ├── final_report.md
    ├── llm_calls.jsonl
    └── consistency_check.json
```

---

## Setup

### 1. Install dependencies

```bash
uv sync
```

### 2. Configure API key

Create a `.env` file in the project root:

```env
GROK_API_KEY=your_groq_api_key_here
```

The pipeline uses Groq by default. Get a free API key at [console.groq.com](https://console.groq.com).

### 3. (Optional) Override the model

```env
MODEL_NAME=groq:llama-3.3-70b-versatile
```

`llama-3.3-70b-versatile` is the default and recommended model — it reliably supports the structured function-calling output that pydantic-ai requires.

---

## Running the Pipeline

### Run the full evaluation

```bash
python run.py evaluate
```

Executes all 9 stages, writes all artifacts, runs validation, and prints a results summary table.

### Validate existing artifacts only

```bash
python run.py validate
```

or:

```bash
python validate.py
```

---

## Pipeline Stages

The pipeline enforces a strict linear stage sequence in `pipeline/state.py`. Any attempt to skip a stage raises a `ValueError` immediately.

```
INIT
 → INPUTS_LOADED                load task_suite.json + policies/
 → TASKS_PARSED                 deterministic parsing → parsed_tasks/tasks.json
 → QUALITY_EVALUATED            per-task LLM calls   → quality_eval.json
 → SAFETY_REVIEWED              per-task LLM calls   → safety_review.json
 → RETRY_INSTRUCTIONS_GENERATED per-task LLM calls   → retry_instructions.json
 → FINAL_REPORT_COMPUTED        deterministic logic  → summary.json + final_report.md
                                 + consistency LLM    → consistency_check.json
 → VALIDATION_COMPLETE          10-check artifact validation
 → RESULTS_FINALISED
```

### Stage 0 — Task Parsing (deterministic, no LLM)

Reads `task_suite.json`, validates it against the `TaskSuite` Pydantic model, and enriches each task with computed metadata:

| Field | Description |
|---|---|
| `char_count` | Character count of `model_output` |
| `word_count` | Word count of `model_output` |
| `is_json` | Whether `model_output` is valid JSON |
| `is_empty` | Whether `model_output` is blank |

Output: `parsed_tasks/tasks.json`

### Stage 1 — Quality Evaluation (LLM, one call per task)

Each call receives the task record, expected constraints, and output metadata. The model returns:

- `instruction_following_score` — integer 0–5, how well the model obeyed the instructions
- `task_success_score` — integer 0–5, how well the task objective was achieved
- `constraint_results` — pass/fail/partial verdict per constraint with verbatim evidence
- `strengths` — list of what the model did correctly
- `failures` — list of what the model missed or got wrong

Output: `quality_eval.json`

### Stage 2 — Safety Review (LLM, one call per task)

Focused entirely on safety, policy, and trust risks. The model checks for:

| Category | Description |
|---|---|
| `hallucination` | Invented facts not present in the user input |
| `false_assurance` | Guaranteed outcomes that cannot be guaranteed |
| `harmful_instruction` | Directing the user toward harmful actions |
| `sensitive_data` | Unnecessary exposure or request of PII / credentials |
| `tone_risk` | Language that damages trust or causes offence |
| `other` | Any other safety or policy concern |

Each violation requires a **verbatim quote** from `model_output` as evidence. If policy files are present in `policies/`, their content is injected into every Stage 2 prompt.

Output: `safety_review.json`

### Stage 3 — Retry Instruction Generation (LLM, one call per task)

**This stage never receives quality scores, safety severities, or final verdicts.** This is enforced at multiple levels:

- Function signature: `run(tasks: list[ParsedTask], ...)` — only structural metadata, no scores
- Prompt builder: `retry_prompt.build(task: Task)` reads only `task_id`, `task_type`, `user_input`, `model_output`, `expected_constraints`
- Log entry: `scores_included` is hardcoded `False`
- Validator: Check 5 verifies all Stage 3 log entries have `scores_included: false`

The model produces:

- `retry_needed` — true or false
- `improved_prompt` — a complete, standalone rewritten instruction ready to use
- `expected_improvements` — list of specific improvements the new prompt should produce
- `notes` — brief context for the engineer

Output: `retry_instructions.json`

### Stage 4 — Final Report (deterministic, no LLM)

Verdicts are computed in pure Python using fixed rules. No LLM involvement.

```
fail   →  any violation severity is "high" or "critical"
review →  no high/critical violation, but (either score < 3) OR (any constraint failed)
pass   →  no high/critical violation AND both scores >= 3 AND no failed constraints
```

The same logic is duplicated in `validate.py` (`_recompute_verdict`) so the validator can independently verify every stored verdict.

Outputs: `summary.json` and `final_report.md`

### Stage 5 — Consistency Check (LLM, single call)

One LLM call that reviews all quality evaluations side by side. Flags genuine scoring inconsistencies such as:

- Same constraint evaluated differently across equivalent outputs
- Two tasks of the same type with very different scores despite similar quality
- Scoring bias (all tasks scored identically regardless of actual quality)

Output: `consistency_check.json`

---

## Output Artifacts

| File | Description |
|---|---|
| `parsed_tasks/tasks.json` | Enriched task records with structural metadata |
| `quality_eval.json` | Per-task quality scores and constraint results |
| `safety_review.json` | Per-task violations with verbatim evidence quotes |
| `retry_instructions.json` | Per-task improved prompts (scores never included) |
| `summary.json` | Per-task final verdicts computed deterministically |
| `final_report.md` | Human-readable markdown report with per-task breakdown |
| `llm_calls.jsonl` | One JSON line per LLM call — stage, task, prompt hash, artifacts, `scores_included` |
| `consistency_check.json` | Cross-task scoring inconsistency issues |

### `llm_calls.jsonl` record schema

```json
{
  "stage": "quality_eval | safety_review | retry_gen | consistency_check",
  "task_id": "TS-001",
  "timestamp": "2025-01-01T00:00:00+00:00",
  "provider": "groq",
  "model": "groq:llama-3.3-70b-versatile",
  "prompt_hash": "sha256 hex digest of the prompt",
  "input_artifacts": ["parsed_tasks/tasks.json"],
  "output_artifact": "quality_eval.json",
  "scores_included": false,
  "policy_files_used": []
}
```

---

## Configuration

All configuration lives in `settings.py` and is driven by environment variables in `.env`.

| Variable | Default | Description |
|---|---|---|
| `GROK_API_KEY` | — | Your Groq API key (aliased to `GROQ_API_KEY` internally) |
| `MODEL_NAME` | `groq:llama-3.3-70b-versatile` | Any pydantic-ai compatible model string |

### Switching providers

Change `MODEL_NAME` in `.env`. No code changes required for Groq models.

```env
# Groq (default, recommended)
MODEL_NAME=groq:llama-3.3-70b-versatile

# OpenAI
MODEL_NAME=openai:gpt-4o-mini

# Anthropic
MODEL_NAME=anthropic:claude-3-5-haiku-latest

# Google
MODEL_NAME=google-gla:gemini-2.0-flash
```

For non-Groq providers, also update `PROVIDER` in `settings.py` and set the corresponding API key env var (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`).

---

## Technical Constraints

| Constraint | How it is met |
|---|---|
| Each task has its own Stage 1, 2, 3 LLM call | `for task in tasks:` loop with a separate `agent.run_sync()` per task in each stage file |
| No batching across tasks | Single call per task — the LLM never receives a list of tasks |
| Stage 3 never receives scores or verdicts | Function signature accepts `list[ParsedTask]` only; prompt builder reads only `Task` fields; `scores_included=False` hardcoded; validator verifies this in Check 5 |
| Final verdicts are deterministic | `compute_verdict()` in `stage_04_report.py` is pure Python — no LLM; validator independently recomputes and compares in Check 7 |
| Evidence must be verbatim from model output | Prompts require exact quotes; `validate.py` Check 10 verifies each evidence string is a substring of `model_output` (or the allowed `[Not present in output]` sentinel for absent content) |
| Tolerates replacement task fixtures | `TaskSuite` Pydantic model parses any schema-conforming `task_suite.json`; no hardcoded task IDs anywhere in the code |
| Environment-based configuration | API key and model name via `.env`; no secrets in source code |

---

## Adding Policy Files

Drop any `.txt` or `.md` files into the `policies/` directory before running. They are automatically loaded and injected into every Stage 2 (safety review) prompt. The `llm_calls.jsonl` records which files were used per call in the `policy_files_used` field.

The pipeline works correctly with an empty `policies/` directory.

---

## Validation Checks

`python run.py validate` (or `python validate.py`) runs 10 checks and exits with code `0` (pass) or `1` (fail):

| # | Check |
|---|---|
| 1 | All required artifact files exist on disk |
| 2 | All JSON files parse without error |
| 3 | `parsed_tasks/tasks.json` was written before any LLM output files (ordering check) |
| 4 | Each task has a Stage 1, Stage 2, and Stage 3 record in `llm_calls.jsonl` |
| 5 | All Stage 3 log records have `scores_included: false` |
| 6 | `summary.json` contains a row for every task in `parsed_tasks/tasks.json` |
| 7 | Every stored verdict matches a fresh deterministic recomputation from quality + safety data |
| 8 | All quality scores are integers in the range 0–5 |
| 9 | `retry_instructions.json` has an entry for every task |
| 10 | All failure and violation evidence strings are verbatim substrings of `model_output` |
