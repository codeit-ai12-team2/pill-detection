//
//  CameraVM.swift
//  Pillaw
//
//  Created by Yuventius Choi on 7/7/26.
//

import AVFoundation
import Observation
import SwiftData
import os

private let logger = Logger(
    subsystem: Bundle.main.bundleIdentifier ?? "Pillaw",
    category: "CameraVM"
)

@Observable
final class CameraVM {
    enum PermissionState {
        case unknown
        case granted
        case denied
    }

    /// 촬영 화면의 표시 모드. 촬영 전에는 라이브 프리뷰, 촬영 후에는 정지 화면 + 결과.
    enum Mode {
        case camera
        case result
    }

    /// 카메라 프리뷰 위에 그릴 bounding box 하나.
    struct DetectionBox: Identifiable {
        let id = UUID()
        /// 프레임 기준 정규화 좌표 (좌상단 원점, 0~1)
        let rect: CGRect
        let name: String?
        let confidence: Float
    }

    /// 촬영된 프레임에서 감지된 알약 하나. 화면 위쪽부터 순서대로 번호가 매겨진다.
    struct CapturedDetection: Identifiable, Equatable {
        let id = UUID()
        let number: Int
        /// 프레임 기준 정규화 좌표 (좌상단 원점, 0~1)
        let rect: CGRect
        /// DB에서 찾은 알약 정보. 매핑이 없거나 저장되지 않은 알약이면 nil.
        let pill: Pill?
        let confidence: Float
        /// 첫 번째 용법 (dosage_all[0]). 용법 정보가 없으면 nil.
        var firstDosage: String? = nil
    }

    private let cameraRepo: CameraRepo

    var permission: PermissionState = .unknown

    var mode: Mode = .camera

    var isTorchOn = false

    /// 촬영된 정지 프레임. result 모드에서만 값이 있다.
    var capturedImage: CGImage?

    /// 촬영 프레임 크기(픽셀). bbox를 aspect-fill 화면 좌표로 변환할 때 사용.
    var capturedFrameSize: CGSize = .zero

    /// 촬영 프레임의 감지 결과 (위에서부터 번호순)
    var capturedDetections: [CapturedDetection] = []

    /// 현재 카메라에 잡혀 있는 알약 목록 (먼저 감지된 순, 중복 없음)
    var detectedPills: [Pill] = []

    /// bounding box 표시 여부 (카메라 화면의 토글 버튼으로 제어)
    var showsBoundingBoxes = false

    /// 현재 프레임의 bounding box 목록. showsBoundingBoxes가 켜져 있을 때만 채워진다.
    var detectionBoxes: [DetectionBox] = []

    /// 감지에 사용된 프레임 크기(픽셀). bbox를 aspect-fill 프리뷰 좌표로 변환할 때 사용.
    var detectionFrameSize: CGSize = .zero

    /// category_id → Pill 조회 결과 캐시. 프레임마다 SwiftData를 다시 조회하지 않기 위함.
    private var pillCache: [String: Pill] = [:]

    /// category_id → 마지막으로 감지된 시각
    private var lastSeenAt: [String: TimeInterval] = [:]

    /// 목록에 표시 중인 category_id (먼저 감지된 순서 유지)
    private var visibleCategoryIds: [String] = []

    /// 감지가 끊겨도 이 시간 동안은 목록에 유지해 깜빡임을 줄인다.
    private let retentionInterval: TimeInterval = 1

    /// 목록에 표시할 최소 신뢰도. 이보다 낮은 감지는 목록에 올리지 않는다.
    /// (bbox 오버레이는 튜닝을 위해 모델 임계값(0.25) 이상을 전부 보여준다)
    private let minimumListConfidence: Float = 0.75

    var session: AVCaptureSession {
        cameraRepo.session
    }

    var isDetectionAvailable: Bool {
        cameraRepo.isDetectionAvailable
    }

    init(cameraRepo: CameraRepo) {
        self.cameraRepo = cameraRepo
    }

    func startCamera() async {
        guard await cameraRepo.requestPermission() else {
            permission = .denied
            return
        }
        permission = .granted
        await cameraRepo.start()
    }

    func stopCamera() async {
        await cameraRepo.stop()
    }

    /// 감지 스트림을 구독해 카메라에 잡힌 알약을 목록에 반영한다.
    /// 먼저 감지된 순서를 유지하고, 감지가 끊긴 알약은 retentionInterval 뒤에 제거한다.
    func startDetection(context: ModelContext) async {
        for await frame in cameraRepo.detections() {
            let now = Date.now.timeIntervalSinceReferenceDate

            for detection in frame.detections where detection.confidence >= minimumListConfidence {
                guard let id = detection.categoryId else { continue }
                if lastSeenAt[id] == nil {
                    visibleCategoryIds.append(id)
                }
                lastSeenAt[id] = now
            }

            visibleCategoryIds.removeAll { id in
                guard let seen = lastSeenAt[id], now - seen <= retentionInterval else {
                    lastSeenAt[id] = nil
                    return true
                }
                return false
            }

            fetchMissingPills(visibleCategoryIds, context: context)

            let pills = visibleCategoryIds.compactMap { pillCache[$0] }
            if pills.map(\.itemSeq) != detectedPills.map(\.itemSeq) {
                detectedPills = pills
            }

            updateDetectionBoxes(with: frame)
        }
    }

    func toggleTorch() async {
        isTorchOn = await cameraRepo.setTorch(!isTorchOn)
    }

    /// 현재 프레임을 촬영하고 감지 결과에 위에서부터 번호를 매겨 result 모드로 전환한다.
    /// - Parameter viewSize: 프리뷰가 표시되는 화면 크기.
    ///   aspect-fill로 잘려나가 화면에 보이지 않는 영역의 감지는 결과에서 제외한다.
    func capture(viewSize: CGSize, context: ModelContext) async {
        guard let frame = await cameraRepo.capture() else { return }

        if isTorchOn {
            isTorchOn = await cameraRepo.setTorch(false)
        }

        let visible = visibleRect(frameSize: frame.size, viewSize: viewSize)

        // Vision 좌표(좌하단 원점) → SwiftUI 좌표(좌상단 원점)
        var converted: [(rect: CGRect, detection: PillDetection)] = frame.detections.compactMap { detection in
            let box = detection.boundingBox
            let rect = CGRect(
                x: box.minX,
                y: 1 - box.maxY,
                width: box.width,
                height: box.height
            )
            // 중심점이 화면에 보이지 않는 감지는 제외
            guard visible.contains(CGPoint(x: rect.midX, y: rect.midY)) else { return nil }
            return (rect: rect, detection: detection)
        }
        // 화면 위쪽부터 순서대로 번호를 매긴다 (같은 높이면 왼쪽 우선)
        converted.sort { lhs, rhs in
            lhs.rect.minY == rhs.rect.minY
                ? lhs.rect.minX < rhs.rect.minX
                : lhs.rect.minY < rhs.rect.minY
        }

        fetchMissingPills(converted.compactMap { $0.detection.categoryId }, context: context)

        let itemSeqs = converted.compactMap { item in
            item.detection.categoryId.flatMap { pillCache[$0]?.itemSeq }
        }
        let dosages = (try? PillDetail.firstDosages(for: itemSeqs, context: context)) ?? [:]

        capturedDetections = converted.enumerated().map { index, item in
            let pill = item.detection.categoryId.flatMap { pillCache[$0] }
            return CapturedDetection(
                number: index + 1,
                rect: item.rect,
                pill: pill,
                confidence: item.detection.confidence,
                firstDosage: pill.flatMap { dosages[$0.itemSeq] }
            )
        }
        capturedImage = frame.image
        capturedFrameSize = frame.size
        mode = .result
    }

    /// 프레임이 aspect-fill로 표시될 때 실제 화면에 보이는 영역 (프레임 기준 정규화 좌표, 좌상단 원점).
    /// 프레임과 화면의 비율 차이로 잘려나가는 가장자리를 제외한 부분이다.
    private func visibleRect(frameSize: CGSize, viewSize: CGSize) -> CGRect {
        let full = CGRect(x: 0, y: 0, width: 1, height: 1)
        guard frameSize.width > 0, frameSize.height > 0,
              viewSize.width > 0, viewSize.height > 0 else { return full }

        let scale = max(
            viewSize.width / frameSize.width,
            viewSize.height / frameSize.height
        )
        let visibleWidth = min(1, viewSize.width / (frameSize.width * scale))
        let visibleHeight = min(1, viewSize.height / (frameSize.height * scale))
        return CGRect(
            x: (1 - visibleWidth) / 2,
            y: (1 - visibleHeight) / 2,
            width: visibleWidth,
            height: visibleHeight
        )
    }

    /// 촬영 결과를 버리고 라이브 카메라로 돌아간다.
    func returnToCamera() {
        mode = .camera
        capturedImage = nil
        capturedDetections = []
    }

    private func fetchMissingPills(_ ids: [String], context: ModelContext) {
        let missingIds = ids.filter { pillCache[$0] == nil }
        guard !missingIds.isEmpty else { return }

        do {
            let descriptor = FetchDescriptor<Pill>(
                predicate: #Predicate { missingIds.contains($0.categoryId) }
            )
            for pill in try context.fetch(descriptor) {
                pillCache[pill.categoryId] = pill
            }
        } catch {
            logger.error("감지된 알약 조회 실패: \(String(describing: error), privacy: .public)")
        }
    }

    private func updateDetectionBoxes(with frame: DetectionFrame) {
        guard showsBoundingBoxes else {
            if !detectionBoxes.isEmpty { detectionBoxes = [] }
            return
        }

        detectionFrameSize = frame.size
        detectionBoxes = frame.detections.map { detection in
            // Vision 좌표(좌하단 원점) → SwiftUI 좌표(좌상단 원점)
            let box = detection.boundingBox
            return DetectionBox(
                rect: CGRect(
                    x: box.minX,
                    y: 1 - box.maxY,
                    width: box.width,
                    height: box.height
                ),
                name: detection.categoryId.flatMap { pillCache[$0]?.itemName },
                confidence: detection.confidence
            )
        }
    }
}
