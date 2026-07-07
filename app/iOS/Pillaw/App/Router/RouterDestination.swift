//
//  RouterDestination.swift
//  Pillaw
//
//  Created by Yuventius Choi on 7/7/26.
//
import SwiftUI

enum RouterDestination {
    @ViewBuilder
    static func view(for route: Route) -> some View {
        switch route {
        case .camera:
            CameraView()
        case .pillInfo(let id):
            PillInfoView()
        }
    }
}
