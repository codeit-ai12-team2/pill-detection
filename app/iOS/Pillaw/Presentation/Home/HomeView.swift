//
//  HomeView.swift
//  Pillaw
//
//  Created by Yuventius Choi on 7/7/26.
//

import SwiftUI

struct HomeView: View {
    @Environment(AppRouter.self)
    private var router
    
    @State
    private var vm: HomeVM
    
    init(vm: HomeVM) {
        _vm = State(initialValue: vm)
    }
    
    var body: some View {
        VStack {
            Text("HomeView")
            Button("Move to CameraView") {
                router.push(.camera)
            }
            Button("Move to PillInfoView") {
                router.push(.pillInfo(id: "0"))
            }
        }
    }
}

#Preview {
    HomeView (
        vm: PreviewContainer.shared.makeHomeVM()
    )
}
