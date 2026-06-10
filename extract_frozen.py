"""Extract the four FROZEN artifacts from BUILD_BRIEF.md Section 4, byte-exactly.

Custody tool: the frozen files are never retyped by hand or by a model; they are
the raw byte ranges of the fenced code blocks under headings 4.1-4.4, written
verbatim (original line endings included). Re-running with a different --outdir
re-extracts for fidelity diffs.

Usage: python extract_frozen.py --source BUILD_BRIEF.md --outdir .
"""
from __future__ import annotations

import argparse
from pathlib import Path

ARTIFACTS = {
    b"### 4.1": "sentinel/dsl.py",
    b"### 4.2": "prompts/sentinel_compile.md",
    b"### 4.3": "prompts/sentinel_judge.md",
    b"### 4.4": "prompts/worker.md",
}


def extract(source: Path, outdir: Path) -> list[Path]:
    lines = source.read_bytes().splitlines(keepends=True)
    written: list[Path] = []
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        heading = next((h for h in ARTIFACTS if stripped.startswith(h)), None)
        if heading is None:
            i += 1
            continue
        # first fence after the heading
        while lines[i].strip() not in (b"```", b"```python"):
            i += 1
        i += 1
        block_start = i
        while lines[i].strip() != b"```":
            i += 1
        target = outdir / ARTIFACTS.pop(heading)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"".join(lines[block_start:i]))
        written.append(target)
        i += 1
    if ARTIFACTS:
        raise SystemExit(f"missing sections: {sorted(ARTIFACTS)}")
    return written


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--outdir", type=Path, required=True)
    args = parser.parse_args()
    for path in extract(args.source, args.outdir):
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
