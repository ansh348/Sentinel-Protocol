# Single entry point for the tripwire-pilot harness (BUILD_BRIEF Section 1.7).
# Windows: run via Git Bash (GNU make 4.4.1, ezwinports). Override PY to point
# at a different interpreter: make test PY=python
PY ?= ../.venv/Scripts/python.exe

.PHONY: test serve

test:
	$(PY) -m pytest tests/ -q

# Manual world server for poking around; never used by comparative runs.
serve:
	$(PY) -m world.server --port 8400
