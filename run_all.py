"""Run the whole pipeline end-to-end: generate -> validate -> detect -> evaluate.

Also supports a reproducibility check that generates twice with the same
seed and compares per-file SHA-256 checksums.

Run:
    python run_all.py                      # starter scale, full pipeline
    python run_all.py --scale full         # full 1M-movement dataset
    python run_all.py --check-repro        # reproducibility check only
    python run_all.py --skip-generate      # re-run validate/detect/evaluate
"""
import argparse
import sys

import generate
import validate
import detect
import evaluate


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scale", default="starter", choices=["starter", "full"])
    ap.add_argument("--seed", type=int, default=20261022)
    ap.add_argument("--check-repro", action="store_true")
    ap.add_argument("--skip-generate", action="store_true")
    args = ap.parse_args()

    if args.check_repro:
        ok = generate.check_repro(args.seed)
        sys.exit(0 if ok else 1)

    print("=" * 70)
    print("STEP 1: GENERATE")
    print("=" * 70)
    if not args.skip_generate:
        generate.run(scale=args.scale, seed=args.seed)

    print("\n" + "=" * 70)
    print("STEP 2: VALIDATE")
    print("=" * 70)
    ok = validate.main()
    if not ok:
        print("[run_all] validation FAILED - stopping")
        sys.exit(1)

    print("\n" + "=" * 70)
    print("STEP 3: DETECT")
    print("=" * 70)
    detect.main()

    print("\n" + "=" * 70)
    print("STEP 4: EVALUATE")
    print("=" * 70)
    evaluate.main()

    print("\n" + "=" * 70)
    print("DONE - see reports/ for all outputs")
    print("=" * 70)


if __name__ == "__main__":
    main()
