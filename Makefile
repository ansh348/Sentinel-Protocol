# Single entry point for the tripwire-pilot harness (BUILD_BRIEF Section 1.7).
# Windows: run via Git Bash (GNU make 4.4.1, ezwinports). Override PY to point
# at a different interpreter: make test PY=python
PY ?= ../.venv/Scripts/python.exe

.PHONY: test serve smoke

test:
	$(PY) -m pytest tests/ -q

# Manual world server for poking around; never used by comparative runs.
serve:
	$(PY) -m world.server --port 8400

# One real sentinel compile on task a1's plan (billed to the subscription).
smoke:
	$(PY) -m sentinel.compile --task tasks/a1.yaml --outdir runs/smoke
