"""Assemble the competition ZIP in the exact required shape:
  output/level1.csv, output/level2.csv
  source/README.md, source/.env.example, source/<project code>
  demo/demo.mp4 (if present)

Run this LAST, after output/level1.csv and output/level2.csv are the real,
final test-data results.

Usage:  python package_submission.py
"""
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STAGE = ROOT / "_submission_stage"
ZIP_PATH = ROOT / "submission.zip"

SOURCE_FILES = [
    "README.md", ".env.example", "requirements.txt", "llm.py", "run.py",
]
SOURCE_DIRS = ["bill_decoder"]
EXCLUDE_DIR_NAMES = {"__pycache__"}
REQUIRED_OUTPUTS = ["output/level1.csv", "output/level2.csv"]


def check_outputs():
    missing = [p for p in REQUIRED_OUTPUTS if not (ROOT / p).exists()]
    if missing:
        raise SystemExit(
            f"Missing required output file(s): {missing}\n"
            "Run the pipeline against the REAL test data first (python run.py all ...)."
        )
    for p in REQUIRED_OUTPUTS:
        full = ROOT / p
        if full.stat().st_size == 0:
            raise SystemExit(f"{p} is empty - did the run actually finish?")


def copy_tree_filtered(src: Path, dst: Path):
    def ignore(dirpath, names):
        return [n for n in names if n in EXCLUDE_DIR_NAMES or n.endswith(".pyc")]
    shutil.copytree(src, dst, ignore=ignore)


def main():
    check_outputs()

    if STAGE.exists():
        shutil.rmtree(STAGE)
    (STAGE / "output").mkdir(parents=True)
    (STAGE / "source").mkdir(parents=True)

    for p in REQUIRED_OUTPUTS:
        shutil.copy2(ROOT / p, STAGE / p)

    for f in SOURCE_FILES:
        src = ROOT / f
        if src.exists():
            shutil.copy2(src, STAGE / "source" / f)
        else:
            print(f"WARNING: {f} not found, skipping")

    for d in SOURCE_DIRS:
        copy_tree_filtered(ROOT / d, STAGE / "source" / d)

    demo = ROOT / "demo" / "demo.mp4"
    for ext in (".mp4", ".mov", ".webm"):
        candidate = ROOT / "demo" / f"demo{ext}"
        if candidate.exists():
            (STAGE / "demo").mkdir(exist_ok=True)
            shutil.copy2(candidate, STAGE / "demo" / candidate.name)
            print(f"Included demo: {candidate.name}")
            break
    else:
        print("No demo video found in demo/ - submitting without one (optional, -5 bonus pts).")

    if ZIP_PATH.exists():
        ZIP_PATH.unlink()
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in STAGE.rglob("*"):
            if path.is_file():
                zf.write(path, path.relative_to(STAGE))

    try:
        shutil.rmtree(STAGE)
    except OSError:
        print(f"(Could not remove staging folder {STAGE} - likely OneDrive syncing it. "
              "Safe to delete manually; the ZIP itself is already written.)")

    size_mb = ZIP_PATH.stat().st_size / 1024 / 1024
    print(f"\nWrote {ZIP_PATH} ({size_mb:.2f} MB)")
    if size_mb > 15:
        print("WARNING: ZIP exceeds the 15 MB limit! Remove the demo video or large files.")
    else:
        print("Size OK (under 15 MB).")

    print("\nContents:")
    with zipfile.ZipFile(ZIP_PATH) as zf:
        for n in sorted(zf.namelist()):
            print(" ", n)


if __name__ == "__main__":
    main()
