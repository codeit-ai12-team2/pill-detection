"""학습된 모델로 test 이미지 전체를 예측해 Kaggle 제출용 submission.csv를 생성합니다.

config/interface.yaml의 imgsz/conf/iou를 사용합니다.

사용 예:
    python predict.py
    python predict.py --output submission_v2.csv
"""

import argparse
import json

import pandas as pd
from common import (
    CLASS_MAPPING_FILE,
    DATA_DIR,
    OUTPUT_DIR,
    YOLO_DIR,
    find_latest_weights,
    get_device,
    load_config,
)
from tqdm import tqdm
from ultralytics import YOLO


def main(output_path: str = "submission.csv"):
    """test 이미지 전체를 예측하고 outputs/yolo/{output_path}에 submission.csv를 저장합니다."""
    device = get_device()
    config = load_config(YOLO_DIR / "config" / "interface.yaml")

    weights_path = find_latest_weights()
    print(f"사용할 가중치 (가장 최근 학습): {weights_path}")

    test_dir = DATA_DIR / "test_images"
    with open(CLASS_MAPPING_FILE, encoding="utf-8") as f:
        class_map = json.load(f)
    reversed_map = {int(v): int(k) for k, v in class_map.items()}

    model = YOLO(weights_path)
    rows = []
    annotation_id = 1

    image_paths = sorted(test_dir.glob("*"), key=lambda p: int(p.stem))
    for image_path in tqdm(image_paths, desc="predict\t"):
        image_id = int(image_path.stem)
        results = model.predict(
            source=image_path,
            imgsz=config["imgsz"],
            conf=config["conf"],
            iou=config["iou"],
            device=device,
            verbose=False,
        )
        for box in results[0].boxes:
            cls = int(box.cls.item())
            score = float(box.conf.item())
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            rows.append(
                {
                    "annotation_id": annotation_id,
                    "image_id": image_id,
                    "category_id": reversed_map[cls],
                    "bbox_x": round(x1),
                    "bbox_y": round(y1),
                    "bbox_w": round(x2 - x1),
                    "bbox_h": round(y2 - y1),
                    "score": score,
                }
            )
            annotation_id += 1

    df = pd.DataFrame(rows)
    out_path = OUTPUT_DIR / output_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)
    print(f"제출 파일 생성 완료: {out_path} ({len(df)}개 예측)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="submission.csv 생성")
    parser.add_argument("--output", default="submission.csv")
    args = parser.parse_args()
    main(output_path=args.output)
