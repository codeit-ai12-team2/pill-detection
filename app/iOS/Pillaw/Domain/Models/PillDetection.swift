//
//  PillDetection.swift
//  Pillaw
//
//  Created by Yuventius Choi on 7/8/26.
//

import Foundation
import CoreGraphics

/// 카메라 프레임 한 장의 감지 결과.
nonisolated struct DetectionFrame: Sendable {
    let detections: [PillDetection]
    /// 감지에 사용된 프레임 크기(픽셀, 회전 적용 후). bbox를 화면 좌표로 변환할 때 사용.
    let size: CGSize
}

/// 촬영 버튼을 눌렀을 때의 정지 프레임과 감지 결과.
nonisolated struct CapturedFrame: Sendable {
    let image: CGImage
    let detections: [PillDetection]
    /// 프레임 크기(픽셀, 회전 적용 후)
    let size: CGSize
}

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
