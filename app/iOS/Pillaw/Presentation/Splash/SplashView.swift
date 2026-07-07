//
//  SplashView.swift
//  Pillaw
//
//  Created by Yuventius Choi on 7/7/26.
//

import SwiftUI

struct SplashView: View {
    @Environment(AppState.self)
    private var appState
    
    var body: some View {
        VStack {
            Text("SplashView")
        }.task {
            try? await Task.sleep(for: .seconds(3))
            appState.root = .home
        }
    }
}

#Preview {
    SplashView()
}
