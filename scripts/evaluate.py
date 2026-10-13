"""Evaluate an exported run using manually verified count/speed/event labels."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from backend.evaluation import evaluate_run


def main():
    parser = argparse.ArgumentParser(description='人工真值对照评估，不生成或推测真值')
    parser.add_argument('--run', required=True, type=Path)
    parser.add_argument('--truth', required=True, type=Path)
    parser.add_argument('--tolerance', type=float, default=.15)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    try:
        result = evaluate_run(args.run, json.loads(args.truth.read_text(encoding='utf-8')), args.tolerance)
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.error(str(error))
    text = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)
    if args.output:
        args.output.write_text(text + '\n', encoding='utf-8')
    print(text)


if __name__ == '__main__':
    main()
