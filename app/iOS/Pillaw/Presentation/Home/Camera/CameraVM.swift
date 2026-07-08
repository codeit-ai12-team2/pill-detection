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

    private let cameraRepo: CameraRepo

    var permission: PermissionState = .unknown

    /// 감지되어 SwiftData에서 조회된 알약 목록 (최근 감지 순, 중복 없음)
    var detectedPills: [Pill] = []

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

    /// 감지 스트림을 구독해 category_id로 SwiftData에서 알약을 찾아 목록에 누적한다.
    func startDetection(context: ModelContext) async {
        for await detections in cameraRepo.detections() {
            let categoryIds = Set(detections.compactMap(\.categoryId))
            let knownIds = Set(detectedPills.map(\.categoryId))
            let newIds = Array(categoryIds.subtracting(knownIds))
            guard !newIds.isEmpty else { continue }

            do {
                let descriptor = FetchDescriptor<Pill>(
                    predicate: #Predicate { newIds.contains($0.categoryId) }
                )
                let pills = try context.fetch(descriptor)
                guard !pills.isEmpty else { continue }
                detectedPills.insert(contentsOf: pills, at: 0)
            } catch {
                logger.error("감지된 알약 조회 실패: \(String(describing: error), privacy: .public)")
            }
        }
    }
}
