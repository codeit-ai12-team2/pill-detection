from __future__ import annotations

import json
import random
from pathlib import Path

import matplotlib.patches as patches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
import yaml
from PIL import Image
from torch.utils.data import Dataset
import matplotlib.font_manager as fm

# 한글 폰트 설정 (나눔고딕 사용)
_KOREAN_FONT_PATH = "/usr/share/fonts/truetype/nanum/NanumGothic.ttf"
if Path(_KOREAN_FONT_PATH).exists():
    fm.fontManager.addfont(_KOREAN_FONT_PATH)
    plt.rcParams["font.family"] = fm.FontProperties(fname=_KOREAN_FONT_PATH).get_name()
plt.rcParams["axes.unicode_minus"] = False 


def _to_numpy(image) -> np.ndarray:
    """PIL Image 또는 (C,H,W) Tensor를 (H,W,3) uint8 ndarray로 변환합니다."""
    if isinstance(image, torch.Tensor):
        img = image.detach().cpu()
        if img.dtype != torch.uint8:
            img = (img.clamp(0, 1) * 255).byte()
        return img.permute(1, 2, 0).numpy()
    # PIL Image
    return np.array(image.convert("RGB"))


def build_color_palette(num_classes: int) -> list[tuple[float, float, float]]:
    """class index → 고정 색상 팔레트를 생성합니다.

    같은 num_classes로 호출하면 항상 동일한 순서로 반환되어
    index i의 색상이 일관되게 유지됩니다.
    """
    colors = []
    for i in range(num_classes):
        hue = (i * 137.508) % 360 / 360  # 황금각 분할로 인접 색상 충돌 방지
        # HSV → RGB (s=0.75, v=0.95 고정)
        s, v = 0.75, 0.95
        h = hue * 6
        c = v * s
        x = c * (1 - abs(h % 2 - 1))
        m = v - c
        if h < 1:
            r, g, b = c, x, 0
        elif h < 2:
            r, g, b = x, c, 0
        elif h < 3:
            r, g, b = 0, c, x
        elif h < 4:
            r, g, b = 0, x, c
        elif h < 5:
            r, g, b = x, 0, c
        else:
            r, g, b = c, 0, x
        colors.append((r + m, g + m, b + m))
    return colors


def visualize_sample(
        image,
        target: dict,
        ax: plt.Axes | None = None,
        show_labels: bool = True,
        line_width: float = 2.0,
        font_size: float = 9.0,
        num_classes: int = 56,
        palette: list[tuple[float, float, float]] | None = None,
) -> plt.Axes:
    """PillDataSet 샘플 하나를 bbox와 함께 그립니다.

    Args:
        image: PIL Image 또는 (C,H,W) Tensor
        target: dataset.__getitem__이 반환하는 target dict
            필수 키: 'boxes' (N,4) [x1,y1,x2,y2], 'labels' Tensor[N], 'label_names' list[str]
        ax: 그릴 Axes. None이면 새로 생성합니다.
        show_labels: bbox 위에 label_name 표시 여부
        line_width: bbox 선 두께
        font_size: label 폰트 크기
        num_classes: 팔레트 크기 (기본 56)
        palette: 미리 생성한 팔레트. None이면 num_classes로 자동 생성합니다.

    Returns:
        그려진 Axes 객체
    """
    img_np = _to_numpy(image)

    if ax is None:
        _, ax = plt.subplots(1, 1, figsize=(8, 8))

    ax.imshow(img_np)
    ax.axis("off")

    boxes = target.get("boxes")
    labels = target.get("labels")
    label_names = target.get("label_names", [])

    if boxes is None or (hasattr(boxes, "__len__") and len(boxes) == 0):
        return ax

    if isinstance(boxes, torch.Tensor):
        boxes = boxes.cpu().numpy()
    if isinstance(labels, torch.Tensor):
        labels = labels.cpu().tolist()

    colors = palette if palette is not None else build_color_palette(num_classes)

    for box, label_id, name in zip(boxes, labels or [], label_names):
        x1, y1, x2, y2 = box
        color = colors[int(label_id) % len(colors)]

        rect = patches.Rectangle(
            (x1, y1),
            x2 - x1,
            y2 - y1,
            linewidth=line_width,
            edgecolor=color,
            facecolor="none",
            )
        ax.add_patch(rect)

        if show_labels and name:
            ax.text(
                x1,
                y1 - 4,
                name,
                color="white",
                fontsize=font_size,
                fontweight="bold",
                bbox=dict(facecolor=color, edgecolor="none", pad=1.5, alpha=0.85),
                clip_on=True,
                )

    image_path = target.get("image_path", "")
    if image_path:
        ax.set_title(str(image_path).split("\\")[-1].split("/")[-1], fontsize=10)

    return ax


def _make_grid_axes(
        n: int, n_cols: int, figsize_per_cell: tuple[float, float]
) -> tuple[plt.Figure, np.ndarray]:
    """n개 항목을 담을 (n_rows, n_cols) 격자 Figure/Axes를 생성합니다."""
    n_rows = (n + n_cols - 1) // n_cols
    fig, axes = plt.subplots(
        n_rows,
        n_cols,
        figsize=(figsize_per_cell[0] * n_cols, figsize_per_cell[1] * n_rows),
    )
    axes_flat = np.array(axes).flatten() if n > 1 else np.array([axes])
    return fig, axes_flat


def visualize_dataset_samples(
        dataset: Dataset,
        indices: list[int] | range | int | None = None,
        n_cols: int = 3,
        figsize_per_cell: tuple[float, float] = (5.0, 5.0),
        num_classes: int = 56,
        **kwargs,
) -> plt.Figure:
    """PillDataSet에서 여러 샘플을 격자 형태로 그립니다.

    Args:
        dataset: PillDataSet 인스턴스 (split='train')
        indices: 시각화할 인덱스 목록. int이면 랜덤으로 그 수만큼 선택. None이면 처음 9개를 사용합니다.
        n_cols: 한 행에 표시할 열 수
        figsize_per_cell: 셀 하나의 (width, height)
        num_classes: 팔레트 크기 (기본 56)
        **kwargs: visualize_sample에 전달할 추가 인자

    Returns:
        matplotlib Figure 객체
    """
    if indices is None:
        indices = list(range(min(9, len(dataset))))  # type: ignore[arg-type]
    elif isinstance(indices, int):
        indices = random.sample(range(len(dataset)), min(indices, len(dataset)))  # type: ignore[arg-type]
    else:
        indices = list(indices)

    palette = build_color_palette(num_classes)

    n = len(indices)
    fig, axes_flat = _make_grid_axes(n, n_cols, figsize_per_cell)

    for ax, idx in zip(axes_flat, indices):
        image, target = dataset[idx]
        visualize_sample(image, target, ax=ax, palette=palette, **kwargs)

    for ax in axes_flat[n:]:
        ax.axis("off")

    fig.tight_layout()
    return fig

def draw_boxes(path: str, boxes: list[list[int]]):
    """
    이미지 bbox 원본, 수정을 동시에 출력합니다.

    Args:
        path: 이미지 경로
        boxes: bbox 좌표 2개의 list (x, y, w, h)

    Returns:
        matplotlib Figure 객체
    """
    colors = ["r", "g"]
    fig, axes = plt.subplots(1, 2, figsize=(10, 5), dpi=150)
    image = plt.imread(path)
    axes[0].imshow(image)
    axes[0].set_title("Original")
    axes[1].imshow(image)
    axes[1].set_title("Modified")
    for idx, box in enumerate(boxes):
        x, y, w, h = box
        axes[idx].add_patch(patches.Rectangle((x, y), w, h, fill=False, edgecolor=colors[idx], linewidth=2))
        axes[idx].axis("off")
    return fig


def load_class_names(class_mapping_path: str | Path, dataset_yaml_path: str | Path) -> dict[int, str]:
    """submission.csv의 category_id를 사람이 읽을 수 있는 이름으로 매핑합니다.

    Args:
        class_mapping_path: {원본 category_id: yolo class index} JSON 경로
        dataset_yaml_path: {yolo class index: 이름}을 담은 dataset.yaml 경로

    Returns:
        {category_id: class_name} 매핑 dict
    """
    with open(class_mapping_path, encoding="utf-8") as f:
        class_mapping = json.load(f)
    with open(dataset_yaml_path, encoding="utf-8") as f:
        names = yaml.safe_load(f)["names"]
    return {int(cat_id): names[idx] for cat_id, idx in class_mapping.items()}


def visualize_submission_sample(
        image_id: int,
        submission: pd.DataFrame,
        test_images_dir: str | Path,
        class_names: dict[int, str] | None = None,
        score_threshold: float = 0.0,
        ax: plt.Axes | None = None,
        **kwargs,
) -> plt.Axes:
    """submission.csv의 예측 bbox를 원본 test 이미지 위에 그립니다.

    Args:
        image_id: 그릴 이미지의 image_id (test_images/{image_id}.png)
        submission: submission.csv를 읽은 DataFrame
        test_images_dir: ai/data/raw/test_images 경로
        class_names: {category_id: 이름} 매핑. None이면 label에 category_id를 사용합니다.
        score_threshold: 이 값 미만인 예측은 제외합니다.
        ax: 그릴 Axes. None이면 새로 생성합니다.
        **kwargs: visualize_sample에 전달할 추가 인자 (line_width, font_size 등)

    Returns:
        그려진 Axes 객체
    """
    image_path = Path(test_images_dir) / f"{image_id}.png"
    image = Image.open(image_path).convert("RGB")

    rows = submission[(submission["image_id"] == image_id) & (submission["score"] >= score_threshold)]

    boxes = rows[["bbox_x", "bbox_y", "bbox_w", "bbox_h"]].to_numpy(dtype=float)
    if len(boxes):
        boxes[:, 2] += boxes[:, 0]  # x2 = x + w
        boxes[:, 3] += boxes[:, 1]  # y2 = y + h

    category_ids = rows["category_id"].tolist()
    label_names = [
        f"{class_names.get(cid, cid) if class_names else cid} {score:.2f}"
        for cid, score in zip(category_ids, rows["score"])
    ]

    target = {
        "boxes": torch.tensor(boxes, dtype=torch.float32),
        "labels": torch.tensor(category_ids, dtype=torch.long),
        "label_names": label_names,
        "image_path": str(image_path),
    }

    return visualize_sample(image, target, ax=ax, **kwargs)


def visualize_submission_samples(
        submission: pd.DataFrame,
        test_images_dir: str | Path,
        image_ids: list[int] | int | None = None,
        class_names: dict[int, str] | None = None,
        score_threshold: float = 0.0,
        n_cols: int = 3,
        figsize_per_cell: tuple[float, float] = (5.0, 5.0),
        **kwargs,
) -> plt.Figure:
    """submission.csv의 예측 bbox를 여러 test 이미지에 대해 격자 형태로 그립니다.

    Args:
        submission: submission.csv를 읽은 DataFrame
        test_images_dir: ai/data/raw/test_images 경로
        image_ids: 그릴 image_id 목록. int이면 랜덤으로 그 수만큼 선택. None이면 submission에 있는 image_id 중 처음 9개를 사용합니다.
        class_names: {category_id: 이름} 매핑
        score_threshold: 이 값 미만인 예측은 제외합니다.
        n_cols: 한 행에 표시할 열 수
        figsize_per_cell: 셀 하나의 (width, height)
        **kwargs: visualize_sample에 전달할 추가 인자

    Returns:
        matplotlib Figure 객체
    """
    unique_ids = sorted(submission["image_id"].unique())

    if image_ids is None:
        image_ids = unique_ids[:9]
    elif isinstance(image_ids, int):
        image_ids = random.sample(unique_ids, min(image_ids, len(unique_ids)))
    else:
        image_ids = list(image_ids)

    n = len(image_ids)
    fig, axes_flat = _make_grid_axes(n, n_cols, figsize_per_cell)

    for ax, image_id in zip(axes_flat, image_ids):
        visualize_submission_sample(
            image_id,
            submission,
            test_images_dir,
            class_names=class_names,
            score_threshold=score_threshold,
            ax=ax,
            **kwargs,
        )

    for ax in axes_flat[n:]:
        ax.axis("off")

    fig.tight_layout()
    return fig