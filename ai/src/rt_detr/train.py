from pathlib import Path

import torch
import yaml
from ultralytics import RTDETR

RTDETR_DIR = Path(__file__).parent


def load_config(config_path):
    """yaml 설정 파일을 읽어 딕셔너리로 반환합니다.

    Args:
        config_path: yaml 파일 경로.

    Returns:
        설정값 딕셔너리.
    """
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_device():
    """사용 가능한 디바이스를 반환합니다.

    Returns:
        CUDA가 있으면 0, MPS가 있으면 'mps', 없으면 'cpu'.
    """
    if torch.cuda.is_available():
        print("CUDA is available. Using GPU.")
        return 0
    if torch.backends.mps.is_available():
        print("MPS is available. Using MPS.")
        return "mps"
    print("CUDA or MPS is not available. Using CPU.")
    return "cpu"


def main(model_name="rtdetr"):
    device = get_device()

    train_config = load_config(RTDETR_DIR / "train.yaml")
    model_config = load_config(RTDETR_DIR / "rtdetr.yaml")

    config = {**train_config, **model_config}

    model_pt = config.pop("model")
    config["data"] = str((RTDETR_DIR / config["data"]).resolve())

    model = RTDETR(model_pt)
    model.train(
        **config,
        device=device,
        project=str(RTDETR_DIR / "runs/detect"),
    )


if __name__ == "__main__":
    main()
