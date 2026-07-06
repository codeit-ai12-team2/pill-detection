from pathlib import Path

import torch
import yaml
from ultralytics import YOLO

YOLO_DIR = Path(__file__).parent


def load_config(config_path) -> dict:
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_device() -> int | str:
    if torch.cuda.is_available():
        print("CUDA is available. Using GPU.")
        return 0
    if torch.backends.mps.is_available():
        print("MPS is available. Using MPS.")
        return "mps"
    print("CUDA or MPS is not available. Using CPU.")
    return "cpu"


def main(model_name: str = "yolo11s"):
    device = get_device()

    train_config = load_config(YOLO_DIR / "train.yaml")
    model_config = load_config(YOLO_DIR / f"{model_name}.yaml")

    config = {**train_config, **model_config}

    model_pt = YOLO_DIR / config.pop("model")
    config["data"] = str((YOLO_DIR / config["data"]).resolve())

    model = YOLO(model_pt)
    model.train(
        **config,
        device=device,
        project=str(YOLO_DIR / "runs/detect"),
    )


if __name__ == "__main__":
    main()