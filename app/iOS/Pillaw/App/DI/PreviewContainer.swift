//
//  PreviewContainer.swift
//  Pillaw
//
//  Created by Yuventius Choi on 7/7/26.
//

final class PreviewContainer {
    static let shared = PreviewContainer()

    func makeHomeVM() -> HomeVM {
        HomeVM()
    }

    func makeCameraVM() -> CameraVM {
        CameraVM(
            cameraRepo: CameraRepoImpl(
                detector: PillDetectorRepoImpl(mappings: [])
            )
        )
    }

    func makeSplashVM() -> SplashVM {
        SplashVM(
            pillRepo: PillRepoImpl(networkClient: NetworkClientImpl()),
            classMappingCSV: """
            class_index,dl_name,category_id,item_seq
            0,보령부스파정 5mg,1900,198700706
            """
        )
    }
}
