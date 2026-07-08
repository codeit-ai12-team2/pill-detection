//
//  AppContainer.swift
//  Pillaw
//
//  Created by Yuventius Choi on 7/7/26.
//

import Foundation

final class AppContainer {
    static let shared = AppContainer()

    private lazy var pillDetector: PillDetectorRepo = PillDetectorRepoImpl(
        mappings: ClassMapping.parse(csv: classMappingCSV)
    )
    private lazy var cameraRepo: CameraRepo = CameraRepoImpl(detector: pillDetector)
    private lazy var networkClient: NetworkClient = NetworkClientImpl()
    private lazy var pillRepo: PillRepo = PillRepoImpl(networkClient: networkClient)

    /// 번들 리소스 로딩은 조립 지점의 책임 — Data 레이어는 문자열만 받는다.
    private var classMappingCSV: String {
        guard
            let url = Bundle.main.url(forResource: "class_mapping", withExtension: "csv"),
            let content = try? String(contentsOf: url, encoding: .utf8)
        else { return "" }
        return content
    }

    func makeHomeVM() -> HomeVM {
        HomeVM()
    }

    func makeCameraVM() -> CameraVM {
        CameraVM(cameraRepo: cameraRepo)
    }

    func makeSplashVM() -> SplashVM {
        SplashVM(pillRepo: pillRepo, classMappingCSV: classMappingCSV)
    }
}
