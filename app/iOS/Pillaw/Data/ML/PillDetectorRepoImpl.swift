//
//  PillDetectorRepoImpl.swift
//  Pillaw
//
//  Created by Yuventius Choi on 7/8/26.
//

import CoreML
import Vision
import os

private let logger = Logger(
    subsystem: Bundle.main.bundleIdentifier ?? "Pillaw",
    category: "PillDetector"
)

/// Ultralytics YOLO 모델을 CoreML로 내보낸 모델로 알약을 감지한다.
/// 모델 파일(yolo.mlpackage)이 아직 프로젝트에 없으면 감지가 비활성화될 뿐
/// 앱 동작에는 영향을 주지 않으므로, 파일이 준비되면 프로젝트에 추가만 하면 된다.
nonisolated final class PillDetectorRepoImpl: PillDetectorRepo, @unchecked Sendable {
    /// 프로젝트에 추가할 CoreML 모델 이름 (yolo.mlpackage → 빌드 시 yolo.mlmodelc)
    private static let modelName = "yolo"
    /// 학습 config의 conf 값과 동일하게 유지
    private static let confidenceThreshold: Float = 0.25

    private let categoryIdByClassIndex: [Int: String]
    private let classIndexByDLName: [String: Int]
    private let modelURL: URL?

    /// 모델 로드 상태. 로드는 첫 detect 호출 시(videoQueue) 수행되므로
    /// 화면 전환 중 메인 스레드를 막지 않는다. detect가 단일 큐에서만
    /// 호출되는 전제로 별도 잠금 없이 접근한다.
    private enum LoadState {
        case notLoaded
        case loaded(VNCoreMLRequest)
        case failed
    }
    private var loadState: LoadState = .notLoaded

    /// 모델 입력 이미지 한 변의 크기(픽셀). end2end 출력 좌표 정규화에 사용.
    private var inputSize: CGFloat = 640

    var isModelAvailable: Bool { modelURL != nil }

    init(mappings: [ClassMapping]) {
        categoryIdByClassIndex = Dictionary(
            mappings.map { ($0.classIndex, $0.categoryId) },
            uniquingKeysWith: { first, _ in first }
        )
        classIndexByDLName = Dictionary(
            mappings.map { ($0.dlName, $0.classIndex) },
            uniquingKeysWith: { first, _ in first }
        )
        modelURL = Bundle.main.url(forResource: Self.modelName, withExtension: "mlmodelc")
        if modelURL == nil {
            logger.error("CoreML 모델(\(Self.modelName, privacy: .public))이 번들에 없어 감지를 비활성화함")
        }
    }

    func detect(in pixelBuffer: CVPixelBuffer) throws -> [PillDetection] {
        guard let request = loadedRequest() else { return [] }

        // configureSession에서 프레임을 세로 방향으로 회전시키므로 orientation은 .up
        let handler = VNImageRequestHandler(cvPixelBuffer: pixelBuffer, orientation: .up)
        try handler.perform([request])

        // nms=True로 내보낸 모델은 Vision이 감지 결과로 변환해준다.
        if let observations = request.results as? [VNRecognizedObjectObservation],
           !observations.isEmpty {
            return decode(observations: observations)
        }

        // nms=False(end2end) 모델은 raw tensor로 직접 디코딩한다.
        if let features = request.results as? [VNCoreMLFeatureValueObservation],
           let array = features.first?.featureValue.multiArrayValue {
            return decode(end2end: array)
        }

        return []
    }

    // MARK: - 결과 디코딩

    private func decode(observations: [VNRecognizedObjectObservation]) -> [PillDetection] {
        observations.compactMap { observation in
            guard
                let top = observation.labels.first,
                top.confidence >= Self.confidenceThreshold,
                let classIndex = classIndex(forLabel: top.identifier)
            else { return nil }

            return PillDetection(
                classIndex: classIndex,
                categoryId: categoryIdByClassIndex[classIndex],
                confidence: top.confidence,
                boundingBox: observation.boundingBox
            )
        }
    }

    /// YOLO end2end 출력(1 × 300 × 6)을 디코딩한다.
    /// 각 행은 [x1, y1, x2, y2, confidence, classIndex]이며
    /// 좌표는 모델 입력 크기(640) 기준 픽셀 값이다.
    private func decode(end2end array: MLMultiArray) -> [PillDetection] {
        let shape = array.shape.map(\.intValue)
        guard let columns = shape.last, columns >= 6 else { return [] }
        let rows = shape.count >= 2 ? shape[shape.count - 2] : 0

        var detections: [PillDetection] = []
        for row in 0..<rows {
            let index: [NSNumber] = shape.count == 3
                ? [0, NSNumber(value: row), 0]
                : [NSNumber(value: row), 0]

            func value(_ column: Int) -> Double {
                var i = index
                i[i.count - 1] = NSNumber(value: column)
                return array[i].doubleValue
            }

            let confidence = Float(value(4))
            guard confidence >= Self.confidenceThreshold else { continue }

            let classIndex = Int(value(5).rounded())
            let x1 = value(0) / inputSize
            let y1 = value(1) / inputSize
            let x2 = value(2) / inputSize
            let y2 = value(3) / inputSize

            // 이미지 좌표(좌상단 원점) → Vision 좌표(좌하단 원점) 변환 + 0~1로 클램프
            let box = CGRect(
                x: x1,
                y: 1 - y2,
                width: x2 - x1,
                height: y2 - y1
            ).intersection(CGRect(x: 0, y: 0, width: 1, height: 1))
            guard !box.isEmpty else { continue }

            detections.append(
                PillDetection(
                    classIndex: classIndex,
                    categoryId: categoryIdByClassIndex[classIndex],
                    confidence: confidence,
                    boundingBox: box
                )
            )
        }
        return detections
    }

    /// Ultralytics 내보내기 설정에 따라 라벨이 클래스 인덱스("3")일 수도,
    /// 클래스 이름(dl_name)일 수도 있어 둘 다 처리한다.
    private func classIndex(forLabel label: String) -> Int? {
        if let index = Int(label) { return index }
        return classIndexByDLName[label]
    }

    /// 로드된 요청을 돌려주고, 아직이면 이 자리에서 로드한다 (첫 호출에서만 느림).
    private func loadedRequest() -> VNCoreMLRequest? {
        switch loadState {
        case .loaded(let request):
            return request
        case .failed:
            return nil
        case .notLoaded:
            guard let modelURL else { return nil }
            do {
                let configuration = MLModelConfiguration()
                // 이 모델은 GPU/ANE용 컴파일이 "MLIR pass manager failed"로 실패하므로
                // CPU 전용으로 실행한다. 모델을 다시 내보내 GPU에서 동작이 확인되면 .all로 변경.
                configuration.computeUnits = .cpuOnly
                let model = try MLModel(contentsOf: modelURL, configuration: configuration)

                if let constraint = model.modelDescription
                    .inputDescriptionsByName["image"]?.imageConstraint {
                    inputSize = CGFloat(constraint.pixelsWide)
                }

                let request = VNCoreMLRequest(model: try VNCoreMLModel(for: model))
                // YOLO 학습 시 letterbox 대신 전체 프레임을 모델 입력 크기에 맞춤
                request.imageCropAndScaleOption = .scaleFill
                loadState = .loaded(request)
                return request
            } catch {
                logger.error("CoreML 모델 로드 실패: \(String(describing: error), privacy: .public)")
                loadState = .failed
                return nil
            }
        }
    }
}
