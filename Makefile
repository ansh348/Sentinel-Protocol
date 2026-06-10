# Single entry point for the tripwire-pilot harness (BUILD_BRIEF Section 1.7).
# Windows: run via Git Bash (GNU make 4.4.1, ezwinports). Override PY to point
# at a different interpreter: make test PY=python
PY ?= ../.venv/Scripts/python.exe

.PHONY: test serve smoke phase0 night0 queue ops

test:
	$(PY) -m pytest tests/ -q

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
