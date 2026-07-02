"""Replication-package archival job (paper Data Availability section).

Zips each artifact family with an INTERNAL per-file SHA-256 manifest, writes the ZIP checksums
to `archives/MANIFEST.sha256` (COMMITTED), and stages the zips under `archives/` (NOT committed;
gitignored via `archives/*.zip`). The author copies the zips off-machine and verifies them
against MANIFEST.sha256. Run traces stay local per the `runs/*` .gitignore convention; this job
is the off-machine bridge the Data Availability section points at.

Families:
  matrix_1b      : runs/matrix_1b                         (confirmatory experiment traces)
  pilot          : run dirs resolved from analysis/matrix_manifest.json (the pilot cell set)
  a7             : runs/a7                                 (benign-noise smoke traces)
  replay_battery : the replay harness CODE + module deps + a run-README (the battery ITSELF,
                   standalone; the traces it verifies live in pilot.zip / matrix_1b.zip)

Internal manifest + zip arcnames are REPO-relative. Zip mtimes make the ZIP bytes
non-reproducible run-to-run, so MANIFEST.sha256 records THIS snapshot's ZIP checksums; the
internal per-file manifest is the content-stable record.
"""
import json, os, sys, hashlib, zipfile
from pathlib import Path

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
RUNS = os.path.join(REPO, "runs")
ARCH = os.path.join(REPO, "archives")

# The replay battery: replay_check.py + everything it imports to run standalone.
BATTERY_PATHS = ["requirements.txt", "trace.py",
                 "analysis/replay_check.py", "analysis/gates.py",
                 "analysis/matrix_manifest.json", "analysis/__init__.py",
                 "world", "sentinel"]

BATTERY_README = """\
# Replay battery (byte-identity replay verification) -- standalone

The battery ITSELF (code + configs) for the paper's Data Availability replication package.

Contents: analysis/replay_check.py (the replay harness) + its module dependencies
(world/, sentinel/, trace.py, analysis/gates.py, analysis/matrix_manifest.json) + requirements.txt.

To run:
  1. Extract pilot.zip and matrix_1b.zip alongside this package so `runs/` exists.
  2. python -m venv .venv ; <venv>/pip install -r requirements.txt
  3. python analysis/replay_check.py
     -> replays each banked injected cell's recorded tool-call sequence against a freshly
        rebuilt world and checks byte-identity (status + body). Writes
        runs/archaeology_v2/replay_check.json.

The banked traces the battery verifies are in pilot.zip / matrix_1b.zip (per the runs/*
traces-stay-local convention).
"""


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def collect(paths):
    """Files under the given paths (files or dirs; absolute or REPO-relative), sorted,
    skipping __pycache__/.pyc and non-existent entries."""
    out = set()
    for p in paths:
        full = p if os.path.isabs(p) else os.path.join(REPO, p)
        if os.path.isfile(full):
            out.add(full)
        elif os.path.isdir(full):
            for root, _, files in os.walk(full):
                if "__pycache__" in root:
                    continue
                out.update(os.path.join(root, fn) for fn in files if not fn.endswith(".pyc"))
    return sorted(out)


def pilot_dirs():
    from analysis.gates import cell_run_dir
    cells = json.load(open(os.path.join(REPO, "analysis", "matrix_manifest.json"), encoding="utf-8"))
    dirs, seen, missing = [], set(), 0
    for c in cells:
        d = cell_run_dir(Path(RUNS), c)
        if d is None:
            missing += 1
        elif str(d) not in seen:
            seen.add(str(d)); dirs.append(str(d))
    return dirs, len(cells), missing


def family_zip(name, paths, extra_files=None):
    files = collect(paths)
    manifest = "\n".join(f"{sha256_file(f)}  {os.path.relpath(f, REPO)}" for f in files)
    zpath = os.path.join(ARCH, f"{name}.zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files:
            z.write(f, arcname=os.path.relpath(f, REPO))
        for arc, content in (extra_files or {}).items():
            z.writestr(arc, content)
        z.writestr(f"MANIFEST_{name}.sha256", manifest + "\n")
    return {"zip": f"{name}.zip", "sha256": sha256_file(zpath),
            "n_files": len(files), "size_bytes": os.path.getsize(zpath),
            "n_dirs": sum(1 for p in paths if os.path.isdir(p if os.path.isabs(p)
                          else os.path.join(REPO, p)))}


def main():
    os.makedirs(ARCH, exist_ok=True)
    fam = {}
    fam["matrix_1b"] = family_zip("matrix_1b", [os.path.join(RUNS, "matrix_1b")])
    pdirs, ncells, missing = pilot_dirs()
    fam["pilot"] = family_zip("pilot", pdirs)
    fam["pilot"].update(manifest_cells=ncells, cells_missing_dir=missing, n_dirs=len(pdirs))
    fam["a7"] = family_zip("a7", [os.path.join(RUNS, "a7")])
    fam["replay_battery"] = family_zip("replay_battery", BATTERY_PATHS,
                                       extra_files={"README_replay_battery.md": BATTERY_README})

    lines = [
        "# Replication-package archive checksums (SHA-256 of each ZIP).",
        "# Zips are staged under archives/ (gitignored) for off-machine copy; verify with:",
        "#   cd archives && sha256sum -c MANIFEST.sha256",
        "# Generated by analysis/archive_replication.py. Trace families (matrix_1b, pilot, a7)",
        "# bundle local runs/ (traces stay local per runs/*); replay_battery bundles the harness",
        "# CODE itself. Each ZIP also carries an internal MANIFEST_<family>.sha256 (per-file).",
        "",
    ]
    order = ("matrix_1b", "pilot", "a7", "replay_battery")
    for k in order:
        f = fam[k]
        extra = (f"   (pilot = {f['manifest_cells']} manifest cells resolved; "
                 f"{f['cells_missing_dir']} had no run dir)") if k == "pilot" else \
                ("   (the replay harness code, standalone)" if k == "replay_battery" else "")
        lines.append(f"{f['sha256']}  {f['zip']}")
        lines.append(f"#   {k}: {f['n_files']} files, {f['size_bytes']} bytes{extra}")
    open(os.path.join(ARCH, "MANIFEST.sha256"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
