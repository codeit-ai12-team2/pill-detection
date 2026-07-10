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
    func detections() -> AsyncStream<DetectionFrame>
    /// 토치(플래시)를 켜거나 끈다. 실제로 적용된 상태를 반환한다.
    func setTorch(_ isOn: Bool) async -> Bool
    /// 현재 프레임을 정지 이미지로 캡처하고 감지 결과와 함께 반환한다.
    func capture() async -> CapturedFrame?
}
