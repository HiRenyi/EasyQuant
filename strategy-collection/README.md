# Strategy Collection

## Directory Structure

```
strategy-collection/
├── validated/          ← Backtest-verified strategies (28 files, tracked in git)
├── README.md           ← This file
└── *.txt, *.py         ← Unverified / pending strategies (local only, not in git)
```

## Usage

1. Place new `.txt` / `.py` strategy files in this directory
2. Run `python scripts/submit_next.py` to submit and backtest
3. Verified strategies are moved to `validated/` subdirectory
