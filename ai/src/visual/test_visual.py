"""
기존 visual 유틸(load_class_names, visualize_submission_samples)을 활용해
submission.csv 예측 결과를 test 이미지 10장씩 그리드로 묶어
ai/data/outputs/test_visual 에 저장

사용 전 확인:
    - 아래 import 경로(from visual import ...)를 실제 모듈 위치에 맞게 수정하세요.
      (예: ai/src/visual/xxx.py 라면 `from visual.xxx import ...` 등)

사용 예시:
    python make_test_visual_grids.py

    # 파일당 이미지 수 / 그리드 열 수 조정 (기본 10장, 5열 2행)
    python make_test_visual_grids.py --per_file 10 --cols 5

    # 처음 30장만 (그리드 3장 분량)
    python make_test_visual_grids.py --max_images 30

    # score 0.3 미만 예측은 제외
    python make_test_visual_grids.py --score_threshold 0.3
"""

import argparse
from pathlib import Path

import pandas as pd

from visual_utils import load_class_names, visualize_submission_samples  

SCRIPT_DIR = Path(__file__).parent


def main():
    ai_dir = (SCRIPT_DIR / "../../").resolve() if (SCRIPT_DIR / "../../data").exists() else Path("ai")

    parser = argparse.ArgumentParser(description="submission.csv 예측 결과를 10장씩 그리드로 시각화")
    parser.add_argument("--csv", type=Path,
                         default=ai_dir / "data/outputs/yolo26l/submission.csv",
                         help="예측 결과 CSV 경로")
    parser.add_argument("--test_images_dir", type=Path,
                         default=ai_dir / "data/raw/test_images",
                         help="테스트 원본 이미지 폴더")
    parser.add_argument("--class_mapping", type=Path,
                         default=ai_dir / "data/processed/yolo/class_mapping.json",
                         help="{원본 category_id: yolo class index} JSON 경로")
    parser.add_argument("--dataset_yaml", type=Path,
                         default=ai_dir / "data/processed/yolo/dataset.yaml",
                         help="{yolo class index: 이름}을 담은 dataset.yaml 경로")
    parser.add_argument("--output_dir", type=Path,
                         default=ai_dir / "data/outputs/test_visual",
                         help="그리드 이미지 저장 폴더")
    parser.add_argument("--score_threshold", type=float, default=0.0,
                         help="이 값 미만 score인 예측은 제외")
    parser.add_argument("--max_images", type=int, default=None,
                         help="시각화할 최대 이미지 수 (미지정 시 전체)")
    parser.add_argument("--image_ids", type=int, nargs="*", default=None,
                         help="특정 image_id만 시각화하고 싶을 때 나열")
    parser.add_argument("--per_file", type=int, default=10,
                         help="한 파일(그리드)에 담을 이미지 수 (기본 10장)")
    parser.add_argument("--cols", type=int, default=5,
                         help="그리드 열 수 (기본 5열 -> per_file=10이면 5x2)")
    parser.add_argument("--figsize_per_cell", type=float, nargs=2, default=(5.0, 5.0),
                         help="셀 하나의 (width, height), inch 단위")
    args = parser.parse_args()

    if not args.csv.exists():
        raise FileNotFoundError(f"CSV 파일을 찾을 수 없습니다: {args.csv}")
    if not args.test_images_dir.exists():
        raise FileNotFoundError(f"이미지 폴더를 찾을 수 없습니다: {args.test_images_dir}")

    submission = pd.read_csv(args.csv)

    class_names = None
    if args.class_mapping.exists() and args.dataset_yaml.exists():
        class_names = load_class_names(args.class_mapping, args.dataset_yaml)
        print(f"클래스 매핑 로드 완료 ({len(class_names)}개 클래스)")
    else:
        print("[경고] class_mapping.json 또는 dataset.yaml을 찾을 수 없어 category_id를 그대로 표시합니다.")

    image_ids = sorted(submission["image_id"].unique())
    if args.image_ids:
        image_ids = [i for i in image_ids if i in set(args.image_ids)]
    if args.max_images:
        image_ids = image_ids[: args.max_images]

    args.output_dir.mkdir(parents=True, exist_ok=True)

    n_files = 0
    for start in range(0, len(image_ids), args.per_file):
        batch_ids = image_ids[start: start + args.per_file]

        fig = visualize_submission_samples(
            submission,
            args.test_images_dir,
            image_ids=batch_ids,
            class_names=class_names,
            score_threshold=args.score_threshold,
            n_cols=args.cols,
            figsize_per_cell=tuple(args.figsize_per_cell),
        )

        n_files += 1
        out_path = args.output_dir / f"grid_{n_files:03d}.png"
        fig.savefig(out_path, bbox_inches="tight")
        print(f"  저장: {out_path} ({len(batch_ids)}장)")

    print(f"완료: 이미지 {len(image_ids)}개 ->  이미지 10개 묶음 파일 {n_files}개 저장 -> {args.output_dir}")


if __name__ == "__main__":
    main()