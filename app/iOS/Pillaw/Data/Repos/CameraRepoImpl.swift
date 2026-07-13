//
//  CameraRepoImpl.swift
//  Pillaw
//
//  Created by Yuventius Choi on 7/7/26.
//

import AVFoundation
import CoreImage
import os

private let logger = Logger(
    subsystem: Bundle.main.bundleIdentifier ?? "Pillaw",
    category: "Camera"
)

nonisolated final class CameraRepoImpl: NSObject, CameraRepo, @unchecked Sendable {
    let session = AVCaptureSession()

    private let detector: PillDetectorRepo

    private let sessionQueue = DispatchQueue(label: "com.pillaw.camera.session")
    private let videoQueue = DispatchQueue(label: "com.pillaw.camera.video")

    private var isConfigured = false
    private var isRunning = false
    private var pendingStop: DispatchWorkItem?
    // 재진입시 2초 delay
    private let stopDelay: TimeInterval = 2

    // sessionQueue에서만 접근. 토치 제어에 사용.
    private var device: AVCaptureDevice?

    // videoQueue에서만 접근
    private var detectionContinuation: AsyncStream<DetectionFrame>.Continuation?
    private var captureContinuation: CheckedContinuation<CapturedFrame?, Never>?
    private let ciContext = CIContext()
    // 마지막 detection 시간
    private var lastDetectionTime: CFAbsoluteTime = 0
    // 감지는 프레임마다 하지 않고 일정 주기로 수행
    private let detectionInterval: CFTimeInterval = 0.3

    var isDetectionAvailable: Bool {
        detector.isModelAvailable
    }

    init(detector: PillDetectorRepo) {
        self.detector = detector
        super.init()
    }

    func requestPermission() async -> Bool {
        switch AVCaptureDevice.authorizationStatus(for: .video) {
        case .authorized:
            return true
        case .notDetermined:
            return await AVCaptureDevice.requestAccess(for: .video)
        default:
            return false
        }
    }

    func start() async {
        await withCheckedContinuation { continuation in
            sessionQueue.async { [self] in
                pendingStop?.cancel()
                pendingStop = nil

                if !isConfigured {
                    configureSession()
                    isConfigured = true
                }

                if !isRunning {
                    session.startRunning()
                    isRunning = true
                }

                continuation.resume()
            }
        }
    }

    func stop() async {
        sessionQueue.async { [self] in
            pendingStop?.cancel()

            let work = DispatchWorkItem { [weak self] in
                guard let self, self.isRunning else { return }
                self.session.stopRunning()
                self.isRunning = false
            }
            pendingStop = work
            sessionQueue.asyncAfter(deadline: .now() + stopDelay, execute: work)
        }
    }

    func detections() -> AsyncStream<DetectionFrame> {
        AsyncStream(bufferingPolicy: .bufferingNewest(1)) { [weak self] continuation in
            self?.videoQueue.async { [weak self] in
                self?.detectionContinuation = continuation
            }
            continuation.onTermination = { [weak self] _ in
                self?.videoQueue.async { [weak self] in
                    self?.detectionContinuation = nil
                }
            }
        }
    }

    func setTorch(_ isOn: Bool) async -> Bool {
        await withCheckedContinuation { continuation in
            sessionQueue.async { [self] in
                guard let device, device.hasTorch else {
                    continuation.resume(returning: false)
                    return
                }
                do {
                    try device.lockForConfiguration()
                    device.torchMode = isOn ? .on : .off
                    device.unlockForConfiguration()
                    continuation.resume(returning: isOn)
                } catch {
                    logger.error("토치 설정 실패: \(String(describing: error), privacy: .public)")
                    continuation.resume(returning: false)
                }
            }
        }
    }

    func capture() async -> CapturedFrame? {
        await withCheckedContinuation { continuation in
            videoQueue.async { [self] in
                // 이미 진행 중인 캡처가 있으면 새 요청은 실패 처리
                guard captureContinuation == nil else {
                    continuation.resume(returning: nil)
                    return
                }
                captureContinuation = continuation
            }
        }
    }

    private func configureSession() {
        session.beginConfiguration()
        defer { session.commitConfiguration() }

        session.sessionPreset = .high

        guard
            let device = AVCaptureDevice.default(
                .builtInWideAngleCamera,
                for: .video,
                position: .back
            ),
            let input = try? AVCaptureDeviceInput(device: device),
            session.canAddInput(input)
        else { return }

        session.addInput(input)
        self.device = device

        let output = AVCaptureVideoDataOutput()
        output.videoSettings = [
            kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32BGRA
        ]
        output.alwaysDiscardsLateVideoFrames = true
        output.setSampleBufferDelegate(self, queue: videoQueue)

        guard session.canAddOutput(output) else { return }
        session.addOutput(output)

        // 프레임을 세로 방향으로 회전시켜 Vision에 .up 방향으로 전달
        if let connection = output.connection(with: .video),
           connection.isVideoRotationAngleSupported(90) {
            connection.videoRotationAngle = 90
        }
    }
}

extension CameraRepoImpl: AVCaptureVideoDataOutputSampleBufferDelegate {
    func captureOutput(
        _ output: AVCaptureOutput,
        didOutput sampleBuffer: CMSampleBuffer,
        from connection: AVCaptureConnection
    ) {
        guard let pixelBuffer = sampleBuffer.imageBuffer else { return }

        if let capture = captureContinuation {
            captureContinuation = nil
            capture.resume(returning: makeCapturedFrame(from: pixelBuffer))
        }

        guard detectionContinuation != nil, detector.isModelAvailable else { return }

        let now = CFAbsoluteTimeGetCurrent()
        guard now - lastDetectionTime >= detectionInterval else { return }
        lastDetectionTime = now

        do {
            let detections = try detector.detect(in: pixelBuffer)
            let frameSize = CGSize(
                width: CVPixelBufferGetWidth(pixelBuffer),
                height: CVPixelBufferGetHeight(pixelBuffer)
            )
            detectionContinuation?.yield(
                DetectionFrame(detections: detections, size: frameSize)
            )
        } catch {
            logger.error("감지 실패: \(String(describing: error), privacy: .public)")
        }
    }

    /// 현재 픽셀 버퍼를 정지 이미지로 변환하고 감지를 수행한다. 모델이 없으면 감지 결과는 비워 둔다.
    private func makeCapturedFrame(from pixelBuffer: CVPixelBuffer) -> CapturedFrame? {
        let ciImage = CIImage(cvPixelBuffer: pixelBuffer)
        guard let cgImage = ciContext.createCGImage(ciImage, from: ciImage.extent) else {
            logger.error("캡처 프레임 이미지 변환 실패")
            return nil
        }

        var detections: [PillDetection] = []
        if detector.isModelAvailable {
            do {
                detections = try detector.detect(in: pixelBuffer)
            } catch {
                logger.error("캡처 프레임 감지 실패: \(String(describing: error), privacy: .public)")
            }
        }

        return CapturedFrame(
            image: cgImage,
            detections: detections,
            size: CGSize(
                width: CVPixelBufferGetWidth(pixelBuffer),
                height: CVPixelBufferGetHeight(pixelBuffer)
            )
        )
    }
}
