//
//  RootView.swift
//  Pillaw
//
//  Created by Yuventius Choi on 7/7/26.
//

import SwiftUI
import SwiftData

struct RootView: View {
    @Environment(AppState.self)
    private var appState
    
    @State private var appRouter = AppRouter()
    
    var body: some View {
        switch appState.root {
        case .splash:
            SplashView(vm: AppContainer.shared.makeSplashVM())
        case .home:
            HomeRouterView()
                .environment(appRouter)
        }
    }
}

#Preview {
    RootView()
        .environment(AppState())
        .modelContainer(for: Pill.self, inMemory: true)
}
