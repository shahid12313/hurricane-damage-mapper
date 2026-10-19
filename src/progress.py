"""Live training progress for both phases, refreshed every 30 seconds.

Usage (from the project root; Ctrl+C to stop watching, training keeps running):

    /opt/anaconda3/bin/python3 -m src.progress
"""

import csv
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path

RUNS = [
    ("Phase 2: find buildings", Path("runs/loc_resnet34"), "src.train", "f1", ["f1", "precision", "recall"]),
    ("Phase 3: classify damage", Path("runs/damage_resnet34"), "src.damage", "score", ["score", "loc_f1", "damage_f1"]),
]
EPOCHS = 30
BAR_WIDTH = 30


def is_running(module):
    return subprocess.run(["pgrep", "-f", f"python3 -m {module}"], capture_output=True).returncode == 0


def read_history(run_dir):
    path = run_dir / "history.csv"
    if not path.exists():
        return []
    with open(path) as f:
        return list(csv.DictReader(f))


def show_run(title, run_dir, module, best_key, columns):
    rows = read_history(run_dir)
    running = is_running(module)
    done = len(rows)
    status = "running" if running else ("finished" if done >= EPOCHS else ("waiting" if done == 0 else "stopped"))

    filled = BAR_WIDTH * done // EPOCHS
    print(f"\n{title}  [{status}]")
    print(f"  [{'#' * filled}{'.' * (BAR_WIDTH - filled)}] epoch {done}/{EPOCHS}")
    if not rows:
        return

    last = rows[-1]
    best = max(rows, key=lambda r: float(r[best_key]))
    print("  latest: " + "  ".join(f"{c}={float(last[c]):.3f}" for c in columns))
    print(f"  best {best_key}: {float(best[best_key]):.3f} (epoch {best['epoch']})")

    minutes = [float(r["minutes"]) for r in rows]
    per_epoch = sum(minutes[-5:]) / len(minutes[-5:])
    if running and done < EPOCHS:
        finish = datetime.now() + timedelta(minutes=per_epoch * (EPOCHS - done))
        print(f"  ~{per_epoch:.1f} min/epoch, expected to finish around {finish:%H:%M}")


def main():
    try:
        while True:
            print("\033[2J\033[H", end="")  # clear the terminal
            print(f"Training progress  (updated {datetime.now():%H:%M:%S}, Ctrl+C to stop watching)")
            for run in RUNS:
                show_run(*run)
            time.sleep(30)
    except KeyboardInterrupt:
        print()


if __name__ == "__main__":
    main()
