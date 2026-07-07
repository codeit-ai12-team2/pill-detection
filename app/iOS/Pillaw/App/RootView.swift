//
//  RootView.swift
//  Pillaw
//
//  Created by Yuventius Choi on 7/7/26.
//

import SwiftUI

struct RootView: View {
    @Environment(AppState.self)
    private var appState
    
    @State private var appRouter = AppRouter()
    
    var body: some View {
        switch appState.root {
        case .splash:
            SplashView()
        case .home:
            HomeRouterView()
                .environment(appRouter)
        }
    }
}

#Preview {
    RootView()
}
