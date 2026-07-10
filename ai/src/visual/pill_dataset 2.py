import json
from pathlib import Path

import torch
from PIL import Image
from torch.utils.data import Dataset


class PillDataSet(Dataset):
    """
    구조:
      data/raw/train_images/{drug_key}_{params}.png
      data/raw/train_annotations/{drug_key}_json/{K-XXXXXX}/{drug_key}_{params}.json
      data/raw/test_images/{number}.png

    JSON 포맷 (COCO-like):
      images[]: 파일명, 약품 메타데이터
      annotations[]: bbox=[x, y, w, h], category_id
      categories[]: 약품명(name), supercategory
    """

    def __init__(self, data_dir: str | Path, split: str = "train", transform=None):
        """
        Args:
            data_dir: ai/data/raw 경로
            split: 'train' 또는 'test'
            transform: torchvision transforms (image에만 적용)
        """
        self.data_dir = Path(data_dir)
        self.split = split
        self.transform = transform

        if split == "train":
            self.image_dir = self.data_dir / "train_images"
            self.ann_dir = self.data_dir / "train_annotations"
            self.samples = self._build_train_index()
        elif split == "test":
            self.image_dir = self.data_dir / "test_images"
            self.samples = self._build_test_index()
        else:
            raise ValueError(f"split은 'train' 또는 'test'여야 합니다. (받은 값: {split!r})")

    # ------------------------------------------------------------------
    # 인덱스 구축
    # ------------------------------------------------------------------

    def _build_train_index(self) -> list[dict]:
        """이미지와 어노테이션을 매핑한 샘플 목록을 반환합니다."""
        # drug_key → annotation 폴더 매핑
        ann_folder_map: dict[str, Path] = {}
        for folder in self.ann_dir.iterdir():
            if folder.is_dir() and folder.name.endswith("_json"):
                drug_key = folder.name[: -len("_json")]
                ann_folder_map[drug_key] = folder

        samples = []
        for img_path in sorted(self.image_dir.glob("*.png")):
            drug_key = self._extract_drug_key(img_path.stem, ann_folder_map)
            if drug_key is None:
                continue

            ann_folder = ann_folder_map[drug_key]
            json_paths = self._find_json_files(ann_folder, img_path.stem)

            if json_paths:
                samples.append({"image_path": img_path, "json_paths": json_paths})

        return samples

    def _build_test_index(self) -> list[dict]:
        """테스트 이미지를 숫자 순서로 반환합니다."""
        return [
            {"image_path": p, "json_paths": []}
            for p in sorted(
                self.image_dir.glob("*.png"), key=lambda p: int(p.stem)
            )
        ]

    def _extract_drug_key(
            self, img_stem: str, ann_folder_map: dict[str, Path]
    ) -> str | None:
        """이미지 파일명 stem에서 drug_key를 추출합니다.

        annotation 폴더 이름({drug_key}_json)을 기준으로 longest-match를 사용합니다.
        """
        for key in ann_folder_map:
            if img_stem.startswith(key + "_"):
                return key
        return None

    def _find_json_files(self, ann_folder: Path, img_stem: str) -> list[Path]:
        """ann_folder 하위 각 약품 폴더에서 img_stem.json을 수집합니다."""
        paths = []
        for pill_folder in ann_folder.iterdir():
            if not pill_folder.is_dir():
                continue
            json_path = pill_folder / f"{img_stem}.json"
            if json_path.exists():
                paths.append(json_path)
        return paths

    # ------------------------------------------------------------------
    # 클래스 목록
    # ------------------------------------------------------------------

    @property
    def classes(self) -> list[str]:
        """데이터셋 전체의 고유 카테고리 이름 목록을 정렬해서 반환합니다."""
        names: set[str] = set()
        for sample in self.samples:
            for json_path in sample["json_paths"]:
                with open(json_path, encoding="utf-8") as f:
                    data = json.load(f)
                for cat in data.get("categories", []):
                    names.add(cat["name"])
        return sorted(names)

    # ------------------------------------------------------------------
    # Dataset 인터페이스
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int):
        sample = self.samples[idx]
        image = Image.open(sample["image_path"]).convert("RGB")

        if self.transform:
            image = self.transform(image)

        if self.split == "test":
            return image, sample["image_path"].name

        target = self._parse_annotations(sample["json_paths"])
        target["image_path"] = str(sample["image_path"])
        return image, target

    # ------------------------------------------------------------------
    # 어노테이션 파싱
    # ------------------------------------------------------------------

    def _parse_annotations(self, json_paths: list[Path]) -> dict:
        """여러 JSON 파일에서 boxes, labels, label_names, meta를 합칩니다."""
        boxes: list[list[float]] = []
        labels: list[int] = []
        label_names: list[str] = []
        meta: list[dict] = []

        for json_path in json_paths:
            with open(json_path, encoding="utf-8") as f:
                data = json.load(f)

            category_name = {c["id"]: c["name"] for c in data.get("categories", [])}

            for ann in data.get("annotations", []):
                x, y, w, h = ann["bbox"]
                boxes.append([x, y, x + w, y + h])  # [x1, y1, x2, y2]
                labels.append(ann["category_id"])
                label_names.append(category_name.get(ann["category_id"], ""))

            meta.extend(data.get("images", []))

        return {
            "boxes": torch.tensor(boxes, dtype=torch.float32),
            "labels": torch.tensor(labels, dtype=torch.long),
            "label_names": label_names,
            "meta": meta,
        }