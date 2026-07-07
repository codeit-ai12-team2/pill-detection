//
//  HomeRouterView.swift
//  Pillaw
//
//  Created by Yuventius Choi on 7/7/26.
//

import SwiftUI

struct HomeRouterView: View {
    @Environment(AppRouter.self)
    private var router
    
    var body: some View {
        @Bindable var router = router
        
        NavigationStack(path: $router.path) {
            HomeView(vm: AppContainer.shared.makeHomeVM())
                .navigationDestination(for: Route.self) {
                    RouterDestination.view(for: $0)
                }
        }
    }
}

#Preview {
    HomeRouterView()
}
