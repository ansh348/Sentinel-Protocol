# Single entry point for the tripwire-pilot harness (BUILD_BRIEF Section 1.7).
# Windows: run via Git Bash (GNU make 4.4.1, ezwinports). Override PY to point
# at a different interpreter: make test PY=python
PY ?= ../.venv/Scripts/python.exe

.PHONY: test taubench serve smoke phase0 night0 queue ops manifest gates freeze

test:
	$(PY) -m pytest tests/ -q

# tau-bench fault-injection harness self-tests (zero-LLM, deterministic; extensions/taubench).
# Kept separate from `test` because they load tau-bench + the litellm-raising guard.
# PYTHONUTF8=1: tau-bench reads its JSON data/README with the platform default codec, which
# breaks on Windows (cp1252) -- UTF-8 mode is the safe default. See extensions/taubench/PORT_NOTES.md.
taubench:
	PYTHONUTF8=1 $(PY) -m pytest extensions/taubench/tests -q

# Manual world server for poking around; never used by comparative runs.
serve:
	$(PY) -m world.server --port 8400

# One real sentinel compile on task a1's plan (billed to the subscription).
smoke:
	$(PY) -m sentinel.compile --task tasks/a1.yaml --outdir runs/smoke

# Protocol Section 6.4: compile the four archetype plans, emit the
# hand-scoring sheet (live calls, billed to the subscription).
phase0:
	$(PY) -m analysis.phase0 --outdir runs/phase0

# Protocol Section 8.1 night 0: enqueue manipulation checks + calibration.
night0:
	$(PY) -m conductor.queue night0

# The overnight supervisor (see RUNBOOK.md).
queue:
	$(PY) -m conductor.queue run

# Morning operations report (ops only; never gate metrics).
ops:
	$(PY) -m conductor.ops_report

# Generate the planned-matrix manifest ONCE before Phase 1; commit it.
manifest:
	$(PY) -m analysis.gates manifest

# Kill-gate table; refuses unless the committed manifest is complete.
gates:
	$(PY) -m analysis.gates gates

# Freeze prereg.md (protocol 6.1/6.2/6.4 verbatim + custody pins); commit it.
freeze:
	$(PY) -m analysis.freeze
