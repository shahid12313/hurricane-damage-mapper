"""Training and evaluation for the building localization model (phase 2).

Model: U-Net with an ImageNet-pretrained ResNet-34 encoder, predicting one channel
(building vs background) from the pre-disaster image.

Metric: pixel F1 over the whole validation set, the same localization score the
xView2 challenge used.

Usage (from the project root; rerunning the same command resumes from the last epoch):

    /opt/anaconda3/bin/python3 -m src.train --epochs 30
"""

import csv
import time
from pathlib import Path

import segmentation_models_pytorch as smp
import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader

from src.dataset import BuildingDataset


def build_model(pretrained=True):
    return smp.Unet("resnet34", encoder_weights="imagenet" if pretrained else None, in_channels=3, classes=1)


def pick_device():
    if torch.cuda.is_available():
        return torch.device("cuda")
    if torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def dice_loss(logits, target, eps=1.0):
    prob = torch.sigmoid(logits)
    inter = (prob * target).sum(dim=(1, 2, 3))
    union = prob.sum(dim=(1, 2, 3)) + target.sum(dim=(1, 2, 3))
    return (1 - (2 * inter + eps) / (union + eps)).mean()


def loss_fn(logits, target):
    # BCE learns per-pixel, Dice keeps small buildings from being ignored next to all the background
    return F.binary_cross_entropy_with_logits(logits, target) + dice_loss(logits, target)


@torch.no_grad()
def evaluate(model, loader, device, threshold=0.5):
    model.eval()
    tp = fp = fn = 0
    for images, masks in loader:
        pred = torch.sigmoid(model(images.to(device))) > threshold
        masks = masks.to(device) > 0.5
        tp += (pred & masks).sum().item()
        fp += (pred & ~masks).sum().item()
        fn += (~pred & masks).sum().item()
    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    f1 = 2 * precision * recall / max(precision + recall, 1e-9)
    return {"f1": f1, "precision": precision, "recall": recall}


def train_localization(
    data_root,
    out_dir,
    train_splits=("tier1",),
    val_split="hold",
    epochs=30,
    batch_size=8,
    lr=3e-4,
    crop=512,
    num_workers=2,
    max_train_tiles=None,
    max_val_tiles=None,
    pretrained=True,
):
    """Train, evaluating on val_split after every epoch.

    Writes to out_dir: last.pt (for resuming), best.pt (highest validation F1) and history.csv.
    If out_dir already has last.pt, training resumes from it.
    """
    data_root, out_dir = Path(data_root), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    device = pick_device()
    use_amp = device.type == "cuda"

    train_ds = BuildingDataset([data_root / s for s in train_splits], crop=crop, augment=True, max_tiles=max_train_tiles)
    val_ds = BuildingDataset([data_root / val_split], crop=None, augment=False, max_tiles=max_val_tiles)
    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True, num_workers=num_workers,
                              pin_memory=use_amp, drop_last=True, persistent_workers=num_workers > 0)
    val_loader = DataLoader(val_ds, batch_size=max(1, batch_size // 4), num_workers=num_workers)
    print(f"device={device}  train tiles={len(train_ds)}  val tiles={len(val_ds)}")

    model = build_model(pretrained).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)
    scaler = torch.amp.GradScaler("cuda", enabled=use_amp)

    start_epoch, best_f1 = 0, 0.0
    last_path = out_dir / "last.pt"
    if last_path.exists():
        ckpt = torch.load(last_path, map_location=device)
        model.load_state_dict(ckpt["model"])
        optimizer.load_state_dict(ckpt["optimizer"])
        scheduler.load_state_dict(ckpt["scheduler"])
        start_epoch, best_f1 = ckpt["epoch"] + 1, ckpt["best_f1"]
        print(f"resumed from epoch {start_epoch}, best F1 so far {best_f1:.4f}")

    history_path = out_dir / "history.csv"
    for epoch in range(start_epoch, epochs):
        model.train()
        started, total_loss = time.time(), 0.0
        for images, masks in train_loader:
            images, masks = images.to(device), masks.to(device)
            optimizer.zero_grad(set_to_none=True)
            with torch.autocast(device_type="cuda", dtype=torch.float16, enabled=use_amp):
                loss = loss_fn(model(images), masks)
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

        if metrics["f1"] > best_f1:
            best_f1 = metrics["f1"]
            torch.save({"model": model.state_dict(), "epoch": epoch, "f1": best_f1}, out_dir / "best.pt")
        torch.save({"model": model.state_dict(), "optimizer": optimizer.state_dict(),
                    "scheduler": scheduler.state_dict(), "epoch": epoch, "best_f1": best_f1}, last_path)

    print(f"done, best validation F1 {best_f1:.4f}")
    return model


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Train the building localization model.")
    parser.add_argument("--data-root", default="data/processed")
    parser.add_argument("--out-dir", default="runs/loc_resnet34")
    parser.add_argument("--train-splits", nargs="+", default=["tier1"])
    parser.add_argument("--val-split", default="hold")
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    train_localization(
        data_root=args.data_root,
        out_dir=args.out_dir,
        train_splits=tuple(args.train_splits),
        val_split=args.val_split,
        epochs=args.epochs,
        batch_size=args.batch_size,
        num_workers=args.workers,
    )
