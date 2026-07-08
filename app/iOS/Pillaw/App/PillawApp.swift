//
//  PillawApp.swift
//  Pillaw
//
//  Created by Yuventius Choi on 7/7/26.
//

import SwiftUI
import SwiftData

@main
struct PillawApp: App {
    @State private var appState = AppState()

    var body: some Scene {
        WindowGroup {
            ZStack {
                Color.bridalHealth
                    .ignoresSafeArea()
                RootView()
                    .environment(appState)
            }
        }
        .modelContainer(for: Pill.self)
    }
}
