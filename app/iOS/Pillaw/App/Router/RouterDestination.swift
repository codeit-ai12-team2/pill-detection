//
//  RouterDestination.swift
//  Pillaw
//
//  Created by Yuventius Choi on 7/7/26.
//
import SwiftUI

enum RouterDestination {
    @ViewBuilder
    static func view (
        for route: Route,
        container: AppContainer? = nil
    ) -> some View {
        switch route {
        case .camera:
            StaticCameraView(vm: (container ?? .shared).makeCameraVM())
        case .pillInfo(let id):
            PillInfoView()
        case .pillInfoBanned:
            PillInfoInvalidView()
        case .favorite:
            FavoriteView(vm: (container ?? .shared).makeFavoriteVM())
        }
    }
}
