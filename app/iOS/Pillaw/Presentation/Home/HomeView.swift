//
//  HomeView.swift
//  Pillaw
//
//  Created by Yuventius Choi on 7/7/26.
//

import SwiftUI
import SwiftData

struct HomeView: View {
    @Environment(AppRouter.self)
    private var router
    
    @Environment(\.modelContext)
    private var modelContext
    
    @State
    private var vm: HomeVM
    
    init(vm: HomeVM) {
        _vm = State(initialValue: vm)
    }
    
    var body: some View {
//        ScrollView {
//            LazyVStack {
//                ForEach(vm.pills, id: \.classIndex) { pill in
//                    PillCardView(pill: pill)
//                        .padding(.horizontal, 20)
//                }
//            }.task {
//                await vm.loadPills(context: modelContext)
//            }
//        }
        VStack {
            Text("HomeView")
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
