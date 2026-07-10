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
//        VStack {
//            Text("HomeView")
//            Text("HomeView")
//            Button("Move to CameraView") {
//                router.push(.camera)
//            }
//            Button("Move to PillInfoView") {
//                router.push(.pillInfo(id: "0"))
//            }
//        }
        VStack(spacing: 30) {
            // header
            HStack(spacing: 10) {
                Image(.pillGun)
                    .resizable()
                    .frame(width: 44, height: 43)
                Text("Pillaw")
                    .font(.cloudSofa(size: 26))
                    .foregroundStyle(.astronaut)
                Spacer()
            }
            
            // body
            VStack(alignment: .leading, spacing: 30) {
                VStack(alignment: .leading, spacing: 12) {
                    Text("어떻게 확인할까요?")
                        .font(.griunMongtori(size: 32))
                        .foregroundStyle(.armadillo)
                    Text("원하는 방법을 선택해 주세요")
                        .font(.griunMongtori(size: 19))
                        .foregroundStyle(.soyaBean)
                }
                VStack(spacing: 14) {
                    Button(action: {
                        router.push(.camera)
                    }) {
                        MenuCardView(icon: .icCamera, iconTint: .steelBlue, iconBGTint: .hawkesBlue, title: "카메라로 인식") {
                            Text("알약을 촬영해서 정보를 확인해요")
                                .font(.griunMongtori(size: 15))
                                .foregroundStyle(.makara)
                        }
                    }
                    Button(action: {
                        router.push(.favorite)
                    }) {
                        MenuCardView(icon: .icStar, iconTint: .webOrange, iconBGTint: .eggWhite, title: "즐겨찾는 알약") {
                            Text("자주 찾는 알약을 바로 확인해요")
                                .font(.griunMongtori(size: 15))
                                .foregroundStyle(.makara)
                        }
                    }
                }
            }
            Spacer()
        }
        .padding(.horizontal, 20)
    }
}

#Preview {
    HomeView (
        vm: PreviewContainer.shared.makeHomeVM()
    )
}
