//
//  FavoriteView.swift
//  Pillaw
//
//  Created by Yuventius Choi on 7/9/26.
//

import SwiftUI
import SwiftData

struct FavoriteView: View {
    @Environment(AppRouter.self)
    private var router
    
    @Environment(\.modelContext)
    private var modelContext

    @State
    private var vm: FavoriteVM

    init(vm: FavoriteVM) {
        _vm = State(initialValue: vm)
    }

    var body: some View {
        ZStack {
            Color.bridalHealth
                .ignoresSafeArea()
            VStack(alignment: .leading) {
                VStack(alignment: .leading, spacing: 5) {
                    Text("즐겨찾는 알약")
                        .font(.griunMongtori(size: 32))
                        .foregroundStyle(.armadillo)
                    Text("이름을 누르면 자세한 정보를 볼 수 있어요")
                        .font(.griunMongtori(size: 15))
                        .foregroundStyle(.makara)
                }
                .padding(.horizontal, 20)
                .padding(.top, 9)
                if vm.favorites.isEmpty {
                    VStack(spacing: 12) {
                        Spacer()
                        Image(.pillGunBanned)
                            .resizable()
                            .frame(width: 230, height: 230)
                        Text("아직 즐겨찾는 알약이 없어요")
                            .font(.griunMongtori(size: 15))
                            .foregroundStyle(.makara)
                            .frame(maxWidth: .infinity)
                        Spacer()
                    }
                } else {
                    ScrollView {
                        LazyVStack(spacing: 12) {
                            ForEach(vm.favorites) { pill in
                                Button (action: {
                                    router.push(.pillInfo(id: pill.itemSeq))
                                }) {
                                    MenuCardView(icon: .icStar, iconTint: .webOrange, iconBGTint: .eggWhite, title: pill.itemName) {
                                        let dosages = vm.dosages(for: pill)
                                        if !dosages.isEmpty {
                                            // UI 변경
                                            PillDurationView(durationContent: dosages[0])
//                                            FlowLayout {
//                                                ForEach(dosages, id: \.self) { dosage in
//                                                    PillDurationView(durationContent: dosage)
//                                                }
//                                            }
                                        }
                                    }
                                }
                            }
                        }
                        .padding(.horizontal, 20)
                    }
                    .padding(.top, 18)
                }
            }
        }
        .onAppear {
            vm.loadFavorites(context: modelContext)
        }
    }
}

#Preview {
    FavoriteView(vm: PreviewContainer.shared.makeFavoriteVM())
        .environment(AppRouter())
        .modelContainer(for: Pill.self, inMemory: true)
}
