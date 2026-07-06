# import json
# from pathlib import Path

# import albumentations as A
# import numpy as np
# import torch
# from PIL import Image
# from torch.utils.data import DataLoader, Dataset, random_split
# from torchvision.transforms import Normalize, ToTensor

# # 1. 설정


# IMAGENET_MEAN = [0.485, 0.456, 0.406]
# IMAGENET_STD = [0.229, 0.224, 0.225]


# BASE_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
# IMAGE_DIR = BASE_DIR / "train_images"
# ANNO_DIR = BASE_DIR / "train_annotations"


# # 2. bbox 범위 초과 보정


# def clip_boxes_xyxy(boxes, img_w, img_h):
#     """[x1, y1, x2, y2] 형식의 박스를 이미지 경계로 보정합니다.

#     EDA에서 발견된 bbox 범위 초과(1건)를 전처리 시점에 보정합니다.

#     Args:
#         boxes: [x1, y1, x2, y2] 형식의 bbox 리스트.
#         img_w: 이미지 너비.
#         img_h: 이미지 높이.

#     Returns:
#         경계로 보정된 bbox 리스트.
#     """
#     clipped = []
#     for x1, y1, x2, y2 in boxes:
#         x1 = max(0, min(x1, img_w))
#         y1 = max(0, min(y1, img_h))
#         x2 = max(0, min(x2, img_w))
#         y2 = max(0, min(y2, img_h))
#         clipped.append([x1, y1, x2, y2])
#     return clipped


# # 3. 증강 + 리사이즈


# # 증강
# # Rotation     : -180 ~ 180
# # Vertical     : 50%
# # Scale        : 0.5 ~ 1.5
# # Translation  : -20% ~ 20%
# # Perspective  : 5e-4 ~ 1e-3
# # Brightness   : -30% ~ 30%
# # Contrast     : -30% ~ 30%
# # Saturation   : -20% ~ 20%
# # Hue          : -5% ~ 5%
# # Gaussian Blur: 20%


# def get_train_aug(size=(640, 640)):
#     """학습용 증강 + 리사이즈 파이프라인을 반환합니다.

#     Args:
#         size: 목표 크기 (width, height).

#     Returns:
#         Rotation, VerticalFlip, Scale, Translation, Perspective,
#         Brightness/Contrast/Saturation/Hue, GaussianBlur를 포함한 Resize 파이프라인.
#     """
#     return A.Compose(
#         [
#             A.Resize(height=size[1], width=size[0]),
#             A.Affine(
#                 rotate=(-180, 180),
#                 scale=(0.5, 1.5),
#                 translate_percent=(-0.2, 0.2),
#                 p=0.8,
#             ),
#             A.VerticalFlip(p=0.5),
#             A.Perspective(scale=(5e-4, 1e-3), p=0.5),
#             A.RandomBrightnessContrast(
#                 brightness_limit=0.3,
#                 contrast_limit=0.3,
#                 p=0.7,
#             ),
#             A.HueSaturationValue(
#                 hue_shift_limit=int(0.05 * 255),
#                 sat_shift_limit=int(0.20 * 255),
#                 val_shift_limit=0,
#                 p=0.5,
#             ),
#             # Gaussian Blur 20%
#             A.GaussianBlur(blur_limit=(3, 7), p=0.2),
#         ],
#         bbox_params=A.BboxParams(
#             format="pascal_voc",  # [x1, y1, x2, y2]
#             label_fields=["labels"],
#             min_visibility=0.3,
#             clip=True,
#         ),
#     )


# def get_val_aug(size=(640, 640)):
#     """검증/테스트용 리사이즈만 적용하는 파이프라인을 반환합니다.

#     Args:
#         size: 목표 크기 (width, height).

#     Returns:
#         Resize만 포함한 파이프라인.
#     """
#     return A.Compose(
#         [
#             A.Resize(height=size[1], width=size[0]),
#         ],
#         bbox_params=A.BboxParams(
#             format="pascal_voc",
#             label_fields=["labels"],
#             min_visibility=0.3,
#             clip=True,
#         ),
#     )


# # 4. 데이터셋


# class PillDataset(Dataset):
#     """알약 이미지와 bbox 라벨을 불러오는 Dataset 클래스.

#     Args:
#         image_dir: 학습 이미지 폴더 경로.
#         anno_dir: 어노테이션(JSON) 폴더 경로.
#         file_stems: 사용할 이미지 파일명(확장자 제외) 리스트.
#         normalize: True면 ImageNet 정규화(RT-DETR), False면 0~1 스케일(YOLO26).
#         augment: albumentations Compose. None이면 증강 없이 원본만 사용.
#     """

#     def __init__(self, image_dir, anno_dir, file_stems, normalize=True, augment=None):
#         self.image_dir = Path(image_dir)
#         self.anno_dir = Path(anno_dir)
#         self.file_stems = file_stems
#         self.augment = augment
#         self.to_tensor = ToTensor()
#         self.normalizer = (
#             Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD) if normalize else None
#         )

#         self._ann_folder_map = {}
#         for folder in self.anno_dir.iterdir():
#             if folder.is_dir() and folder.name.endswith("_json"):
#                 drug_key = folder.name[: -len("_json")]
#                 self._ann_folder_map[drug_key] = folder

#     def __len__(self):
#         return len(self.file_stems)

#     def _find_json_paths(self, file_stem):
#         """파일명에 해당하는 모든 JSON 어노테이션 경로를 찾습니다.

#         Args:
#             file_stem: 이미지 파일명.

#         Returns:
#             매칭되는 JSON 파일 경로 리스트.
#         """
#         drug_key = None
#         for key in self._ann_folder_map:
#             if file_stem.startswith(key + "_"):
#                 drug_key = key
#                 break
#         if drug_key is None:
#             return []

#         ann_folder = self._ann_folder_map[drug_key]
#         json_paths = []
#         for pill_folder in ann_folder.iterdir():
#             if not pill_folder.is_dir():
#                 continue
#             json_path = pill_folder / f"{file_stem}.json"
#             if json_path.exists():
#                 json_paths.append(json_path)
#         return json_paths

#     def __getitem__(self, idx):
#         """이미지 한 장과 bbox 라벨을 불러와 전처리 후 반환합니다.

#         Args:
#             idx: 샘플 인덱스.

#         Returns:
#             (image, target) 튜플. image는 (C,H,W) 텐서, target은
#             'boxes', 'labels', 'label_names' 키를 가진 딕셔너리.
#         """
#         file_stem = self.file_stems[idx]

#         image = Image.open(self.image_dir / f"{file_stem}.png").convert("RGB")
#         img_w, img_h = image.size

#         boxes = []
#         labels = []
#         label_names = []

#         for json_path in self._find_json_paths(file_stem):
#             with open(json_path, encoding="utf-8") as f:
#                 data = json.load(f)

#             category_name = {c["id"]: c["name"] for c in data.get("categories", [])}

#             for ann in data.get("annotations", []):
#                 x, y, w, h = ann["bbox"]
#                 boxes.append([x, y, x + w, y + h])  # [x1, y1, x2, y2]
#                 labels.append(ann["category_id"])
#                 label_names.append(category_name.get(ann["category_id"], ""))

#         boxes = clip_boxes_xyxy(boxes, img_w, img_h)

#         if self.augment is not None:
#             out = self.augment(
#                 image=np.array(image),
#                 bboxes=boxes,
#                 labels=labels,
#             )
#             image = Image.fromarray(out["image"])
#             boxes = out["bboxes"]
#             label_names = [label_names[i] for i in range(len(out["labels"]))]
#             labels = out["labels"]

#         image = self.to_tensor(image)

#         if self.normalizer is not None:
#             image = self.normalizer(image)

#         if len(boxes) == 0:
#             boxes = torch.zeros((0, 4), dtype=torch.float32)
#             labels = torch.zeros((0,), dtype=torch.int64)
#         else:
#             boxes = torch.tensor(boxes, dtype=torch.float32)
#             labels = torch.tensor(labels, dtype=torch.int64)

#         target = {
#             "boxes": boxes,
#             "labels": labels,
#             "label_names": label_names,
#             "image_path": str(self.image_dir / f"{file_stem}.png"),
#         }

#         return image, target


# # 5. 배치 정리 함수 정의


# def collate_fn(batch):
#     """배치 내 (image, target) 쌍을 묶습니다.

#     Args:
#         batch: (image, target) 리스트.

#     Returns:
#         이미지 튜플과 타겟 튜플로 분리된 (images, targets).
#     """
#     return tuple(zip(*batch))


# # 6. 데이터로더


# def get_dataloaders(
#     model="rtdetr", size=(640, 640), batch_size=16, val_ratio=0.2, seed=42
# ):
#     """학습/검증 DataLoader를 함께 반환합니다.

#     Args:
#         model: 'rtdetr' 또는 'yolo'.
#         size: 목표 이미지 크기 (width, height). RT-DETR에만 적용(YOLO는 항상 640x640).
#         batch_size: 배치 크기.
#         val_ratio: 검증 데이터 비율.
#         seed: train/val 분할용 랜덤 시드.

#     Returns:
#         (train_loader, val_loader) 튜플.

#     Raises:
#         ValueError: model이 'rtdetr' 또는 'yolo'가 아닌 경우.
#     """
#     if model not in ("rtdetr", "yolo"):
#         raise ValueError(
#             f"model은 'rtdetr' 또는 'yolo'여야 합니다. (받은 값: {model!r})"
#         )

#     normalize = model == "rtdetr"
#     resize_size = size if model == "rtdetr" else (640, 640)
#     file_stems = sorted(p.stem for p in IMAGE_DIR.glob("*.png"))

#     n_val = int(len(file_stems) * val_ratio)
#     n_train = len(file_stems) - n_val
#     g = torch.Generator().manual_seed(seed)
#     train_stems, val_stems = random_split(file_stems, [n_train, n_val], generator=g)

#     train_set = PillDataset(
#         IMAGE_DIR,
#         ANNO_DIR,
#         list(train_stems),
#         normalize=normalize,
#         augment=get_train_aug(resize_size),
#     )
#     val_set = PillDataset(
#         IMAGE_DIR,
#         ANNO_DIR,
#         list(val_stems),
#         normalize=normalize,
#         augment=get_val_aug(resize_size),
#     )

#     train_loader = DataLoader(
#         train_set, batch_size=batch_size, shuffle=True, collate_fn=collate_fn
#     )
#     val_loader = DataLoader(
#         val_set, batch_size=batch_size, shuffle=False, collate_fn=collate_fn
#     )

#     return train_loader, val_loader


# # 7. 동작 확인


# if __name__ == "__main__":
#     print(f"이미지 경로: {IMAGE_DIR}")
#     print(f"어노테이션 경로: {ANNO_DIR}")

#     train_loader, val_loader = get_dataloaders(
#         model="rtdetr", size=(640, 640), batch_size=16
#     )
#     print(
#         f"\n[RT-DETR 640x640] 학습 {len(train_loader.dataset)}장 / 검증 {len(val_loader.dataset)}장"
#     )

#     images, targets = next(iter(train_loader))
#     print(f"이미지 1장 shape: {images[0].shape}")
#     print(f"첫 번째 타겟 boxes:\n{targets[0]['boxes']}")
#     print(f"첫 번째 타겟 labels: {targets[0]['labels']}")
#     print(f"첫 번째 타겟 label_names: {targets[0]['label_names']}")
