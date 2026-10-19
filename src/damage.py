"""Phase 3: damage classification.

The model sees the pre- and post-disaster images stacked into one 6-channel input and labels
every pixel as background (0), no damage (1), minor (2), major (3) or destroyed (4).
Buildings marked un-classified in xBD are ignored during training.

Scoring follows the xView2 challenge:
    localization F1  pixel F1 for building vs background
    damage F1        harmonic mean of the per-class F1 for the 4 damage levels, on building pixels
    score            0.3 * localization F1 + 0.7 * damage F1

Usage (from the project root; rerunning the same command resumes from the last epoch):

    /opt/anaconda3/bin/python3 -m src.damage --epochs 30
"""

import csv
import time
from pathlib import Path

import cv2
import numpy as np
import segmentation_models_pytorch as smp
import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader, Dataset

from src.dataset import read_rgb, to_tensor
from src.train import pick_device

DAMAGE_NAMES = ["no-damage", "minor-damage", "major-damage", "destroyed"]
IGNORE = 255  # target value for un-classified buildings

# Cross-entropy weights for background, no, minor, major, destroyed. No-damage buildings
# outnumber each damaged class about 8 to 1 (see notebook 01), so damaged pixels count more.
CLASS_WEIGHTS = [0.5, 1.0, 3.0, 3.0, 3.0]


class DamageDataset(Dataset):
    """Pre + post image -> per-pixel damage class, from the files written by src/preprocess.py."""

    def __init__(self, split_dirs, crop=512, augment=True, max_tiles=None):
        self.mask_paths = []
        for d in split_dirs:
            self.mask_paths += sorted(Path(d, "masks").glob("*.png"))
        if max_tiles:
            self.mask_paths = self.mask_paths[:max_tiles]
        self.crop = crop
        self.augment = augment

    def __len__(self):
        return len(self.mask_paths)

    def image_path(self, i, phase):
        mask_path = self.mask_paths[i]
        return mask_path.parent.parent / "images" / f"{mask_path.stem}_{phase}.jpg"

    def __getitem__(self, i):
        pre = read_rgb(self.image_path(i, "pre"))
        post = read_rgb(self.image_path(i, "post"))
        target = cv2.imread(str(self.mask_paths[i]), cv2.IMREAD_GRAYSCALE)
        target[target == 5] = IGNORE

        if self.crop:
            h, w = target.shape
            y = np.random.randint(0, h - self.crop + 1)
            x = np.random.randint(0, w - self.crop + 1)
            pre, post = pre[y:y + self.crop, x:x + self.crop], post[y:y + self.crop, x:x + self.crop]
            target = target[y:y + self.crop, x:x + self.crop]

        if self.augment:
            if np.random.rand() < 0.5:
                pre, post, target = pre[:, ::-1], post[:, ::-1], target[:, ::-1]
            if np.random.rand() < 0.5:
                pre, post, target = pre[::-1], post[::-1], target[::-1]
            k = np.random.randint(4)
            pre, post, target = np.rot90(pre, k), np.rot90(post, k), np.rot90(target, k)

        x = torch.cat([to_tensor(pre), to_tensor(post)])
        return x, torch.from_numpy(target.astype(np.int64))


def build_model(pretrained=True):
    # smp adapts the pretrained first layer to 6 input channels
    return smp.Unet("resnet34", encoder_weights="imagenet" if pretrained else None, in_channels=6, classes=5)


def loss_fn(logits, target, weights):
    return F.cross_entropy(logits, target, weight=weights, ignore_index=IGNORE)


def f1(tp, fp, fn):
    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    return 2 * precision * recall / max(precision + recall, 1e-9)


def predict_classes(logits):
    """Building/background from the full output; damage level chosen among classes 1-4 only."""
    is_building = logits.argmax(1) > 0
    damage = logits[:, 1:5].argmax(1) + 1
    return is_building, damage


@torch.no_grad()
def evaluate(model, loader, device):
    model.eval()
    loc = np.zeros(3)  # tp, fp, fn
    dmg = np.zeros((4, 3))
    for x, target in loader:
        is_building, damage = predict_classes(model(x.to(device)))
        target = target.to(device)
        true_building = target > 0  # includes un-classified buildings
        loc += [(is_building & true_building).sum().item(),
                (is_building & ~true_building).sum().item(),
                (~is_building & true_building).sum().item()]
        scored = (target >= 1) & (target <= 4)
        for c in range(1, 5):
            pred_c, true_c = (damage == c) & scored, (target == c) & scored
            dmg[c - 1] += [(pred_c & true_c).sum().item(),
                           (pred_c & ~true_c).sum().item(),
                           (~pred_c & true_c).sum().item()]

    loc_f1 = f1(*loc)
    class_f1 = [f1(*row) for row in dmg]
    damage_f1 = len(class_f1) / sum(1 / max(v, 1e-6) for v in class_f1)
    metrics = {"score": 0.3 * loc_f1 + 0.7 * damage_f1, "loc_f1": loc_f1, "damage_f1": damage_f1}
    metrics.update({f"f1_{name}": v for name, v in zip(DAMAGE_NAMES, class_f1)})
    # plain floats, since numpy scalars in a checkpoint make torch.load refuse it
    return {k: float(v) for k, v in metrics.items()}


@torch.no_grad()
def building_confusion(model, dataset, device):
    """Building-level 4x4 confusion matrix (rows true, columns predicted).

    Each true building's predicted level is the most common predicted level inside it.
    Buildings are connected regions of the true mask, so touching buildings count as one.
    """
    model.eval()
    matrix = np.zeros((4, 4), dtype=int)
    for i in range(len(dataset)):
        x, target = dataset[i]
        _, damage = predict_classes(model(x[None].to(device)))
        damage, target = damage[0].cpu().numpy(), target.numpy()
        n, components = cv2.connectedComponents(((target >= 1) & (target <= 4)).astype(np.uint8))
        for k in range(1, n):
            inside = components == k
            true_level = np.bincount(target[inside], minlength=5)[1:].argmax()
            pred_level = np.bincount(damage[inside], minlength=5)[1:].argmax()
            matrix[true_level, pred_level] += 1
    return matrix


def train_damage(
    data_root,
    out_dir,
    train_splits=("tier1",),
    val_split="hold",
    epochs=30,
    batch_size=8,
    lr=3e-4,
    crop=512,
    num_workers=4,
    max_train_tiles=None,
    max_val_tiles=None,
    pretrained=True,
):
    """Train, evaluating on val_split after every epoch. Saves last.pt, best.pt (highest score) and history.csv."""
    data_root, out_dir = Path(data_root), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    device = pick_device()
    use_amp = device.type == "cuda"

    train_ds = DamageDataset([data_root / s for s in train_splits], crop=crop, augment=True, max_tiles=max_train_tiles)
    val_ds = DamageDataset([data_root / val_split], crop=None, augment=False, max_tiles=max_val_tiles)
    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True, num_workers=num_workers,
                              pin_memory=use_amp, drop_last=True, persistent_workers=num_workers > 0)
    val_loader = DataLoader(val_ds, batch_size=max(1, batch_size // 4), num_workers=num_workers)
    print(f"device={device}  train tiles={len(train_ds)}  val tiles={len(val_ds)}")

    model = build_model(pretrained).to(device)
    weights = torch.tensor(CLASS_WEIGHTS, device=device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)
    scaler = torch.amp.GradScaler("cuda", enabled=use_amp)

    start_epoch, best_score = 0, 0.0
    last_path = out_dir / "last.pt"
    if last_path.exists():
        ckpt = torch.load(last_path, map_location=device)
        model.load_state_dict(ckpt["model"])
        optimizer.load_state_dict(ckpt["optimizer"])
        scheduler.load_state_dict(ckpt["scheduler"])
        start_epoch, best_score = ckpt["epoch"] + 1, ckpt["best_score"]
        print(f"resumed from epoch {start_epoch}, best score so far {best_score:.4f}")

    history_path = out_dir / "history.csv"
    for epoch in range(start_epoch, epochs):
        model.train()
        started, total_loss = time.time(), 0.0
        for x, target in train_loader:
            x, target = x.to(device), target.to(device)
            optimizer.zero_grad(set_to_none=True)
            with torch.autocast(device_type="cuda", dtype=torch.float16, enabled=use_amp):
                loss = loss_fn(model(x), target, weights)
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
            total_loss += loss.item()
        scheduler.step()

        metrics = evaluate(model, val_loader, device)
        row = {"epoch": epoch + 1, "train_loss": total_loss / len(train_loader), **metrics,
               "lr": optimizer.param_groups[0]["lr"], "minutes": (time.time() - started) / 60}
        print("  ".join(f"{k}={v:.4f}" if isinstance(v, float) else f"{k}={v}" for k, v in row.items()), flush=True)

        is_new_file = not history_path.exists()
        with open(history_path, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(row))
            if is_new_file:
                writer.writeheader()
            writer.writerow(row)

        if metrics["score"] > best_score:
            best_score = metrics["score"]
            torch.save({"model": model.state_dict(), "epoch": epoch, "score": best_score, "metrics": metrics},
                       out_dir / "best.pt")
        torch.save({"model": model.state_dict(), "optimizer": optimizer.state_dict(),
                    "scheduler": scheduler.state_dict(), "epoch": epoch, "best_score": best_score}, last_path)

    print(f"done, best validation score {best_score:.4f}")
    return model


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Train the damage classification model.")
    parser.add_argument("--data-root", default="data/processed")
    parser.add_argument("--out-dir", default="runs/damage_resnet34")
    parser.add_argument("--train-splits", nargs="+", default=["tier1"])
    parser.add_argument("--val-split", default="hold")
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    train_damage(
        data_root=args.data_root,
        out_dir=args.out_dir,
        train_splits=tuple(args.train_splits),
        val_split=args.val_split,
        epochs=args.epochs,
        batch_size=args.batch_size,
        num_workers=args.workers,
    )
