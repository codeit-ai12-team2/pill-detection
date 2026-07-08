//
//  CameraRepo.swift
//  Pillaw
//
//  Created by Yuventius Choi on 7/7/26.
//

import AVFoundation

nonisolated protocol CameraRepo {
    var session: AVCaptureSession { get }
    /// 감지 모델이 준비되어 있는지 여부.
    var isDetectionAvailable: Bool { get }
    func requestPermission() async -> Bool
    func start() async
    func stop() async
    /// 카메라 프레임에서 감지된 알약 목록을 프레임 단위로 전달한다.
    func detections() -> AsyncStream<[PillDetection]>
}
