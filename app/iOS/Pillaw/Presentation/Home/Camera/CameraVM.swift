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

    /// 카메라 프리뷰 위에 그릴 bounding box 하나.
    struct DetectionBox: Identifiable {
        let id = UUID()
        /// 프레임 기준 정규화 좌표 (좌상단 원점, 0~1)
        let rect: CGRect
        let name: String?
        let confidence: Float
    }

    private let cameraRepo: CameraRepo

    var permission: PermissionState = .unknown

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

            fetchMissingPills(context: context)

            let pills = visibleCategoryIds.compactMap { pillCache[$0] }
            if pills.map(\.itemSeq) != detectedPills.map(\.itemSeq) {
                detectedPills = pills
            }

            updateDetectionBoxes(with: frame)
        }
    }

    private func fetchMissingPills(context: ModelContext) {
        let missingIds = visibleCategoryIds.filter { pillCache[$0] == nil }
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
