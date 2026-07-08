//
//  PillDetectorRepo.swift
//  Pillaw
//
//  Created by Yuventius Choi on 7/8/26.
//

import CoreVideo

nonisolated protocol PillDetectorRepo: Sendable {
    /// 번들에 CoreML 모델이 있어 감지가 가능한지 여부.
    var isModelAvailable: Bool { get }
    /// 카메라 프레임 한 장에서 알약을 감지한다. 호출한 스레드에서 동기 수행된다.
    func detect(in pixelBuffer: CVPixelBuffer) throws -> [PillDetection]
}
