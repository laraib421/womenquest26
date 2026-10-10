"""CLI entry point for the WTQ Build Track - Utility Bill Decoder.

Usage:
  # Level 1: extract JSON for every bill, fill level1.csv
  python run.py level1 --bills data/test/bills --template data/test/csv/level1.csv --out output/level1.csv

  # Level 2: answer every question, fill level2.csv (reuses the level1 extraction cache)
  python run.py level2 --bills data/test/bills --template data/test/csv/level2.csv --out output/level2.csv

  # Both, one command
  python run.py all --bills data/test/bills \\
      --level1-template data/test/csv/level1.csv --level1-out output/level1.csv \\
      --level2-template data/test/csv/level2.csv --level2-out output/level2.csv
"""
import argparse
from pathlib import Path

from bill_decoder.pipeline import run_level1, run_level2

DEFAULT_CACHE = "data/.cache"


def main():
    p = argparse.ArgumentParser(description="WTQ Utility Bill Decoder")
    sub = p.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("level1", help="Extract Level 1 JSON for each bill")
    p1.add_argument("--bills", required=True, help="Folder of bill images")
    p1.add_argument("--template", required=True, help="Input level1.csv (bill_id, json)")
    p1.add_argument("--out", required=True, help="Output level1.csv path")
    p1.add_argument("--cache", default=DEFAULT_CACHE)

    p2 = sub.add_parser("level2", help="Answer Level 2 questions for each bill")
    p2.add_argument("--bills", required=True, help="Folder of bill images")
    p2.add_argument("--template", required=True, help="Input level2.csv (bill_id, question_id, question, answer)")
    p2.add_argument("--out", required=True, help="Output level2.csv path")
    p2.add_argument("--cache", default=DEFAULT_CACHE)

    pa = sub.add_parser("all", help="Run level1 then level2")
    pa.add_argument("--bills", required=True)
    pa.add_argument("--level1-template", required=True)
    pa.add_argument("--level1-out", required=True)
    pa.add_argument("--level2-template", required=True)
    pa.add_argument("--level2-out", required=True)
    pa.add_argument("--cache", default=DEFAULT_CACHE)

    args = p.parse_args()

    if args.cmd == "level1":
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        run_level1(args.bills, args.template, args.out, args.cache)
    elif args.cmd == "level2":
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        run_level2(args.bills, args.template, args.out, args.cache)
    elif args.cmd == "all":
        Path(args.level1_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.level2_out).parent.mkdir(parents=True, exist_ok=True)
        run_level1(args.bills, args.level1_template, args.level1_out, args.cache)
        run_level2(args.bills, args.level2_template, args.level2_out, args.cache)


if __name__ == "__main__":
    main()
