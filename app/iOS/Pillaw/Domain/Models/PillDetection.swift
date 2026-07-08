//
//  PillDetection.swift
//  Pillaw
//
//  Created by Yuventius Choi on 7/8/26.
//

import Foundation

/// YOLO 모델이 카메라 프레임에서 감지한 알약 하나의 결과.
nonisolated struct PillDetection: Sendable {
    /// 모델의 클래스 인덱스 (class_mapping.csv의 class_index)
    let classIndex: Int
    /// class_mapping.csv 기준 category_id. 매핑에 없는 클래스면 nil.
    let categoryId: String?
    let confidence: Float
    /// Vision 좌표계(좌하단 원점, 0~1 정규화) 기준 bounding box.
    let boundingBox: CGRect
}
