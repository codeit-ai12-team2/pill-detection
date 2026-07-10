//
//  PillInfoView.swift
//  Pillaw
//
//  Created by Yuventius Choi on 7/7/26.
//

import SwiftUI
import SwiftData
import NukeUI

struct PillInfoView: View {
    let itemSeq: String

    @Environment(\.modelContext)
    private var modelContext

    @State
    private var vm: PillInfoVM

    init(itemSeq: String, vm: PillInfoVM) {
        self.itemSeq = itemSeq
        _vm = State(initialValue: vm)
    }

    var body: some View {
        ZStack {
            Color.bridalHealth
                .ignoresSafeArea()
            VStack(spacing: 38) {
                HStack(spacing: 16) {
                    LazyImage(url: vm.pill?.itemImage.flatMap(URL.init(string:))) { state in
                        if let image = state.image {
                            image
                                .resizable()
                                .scaledToFill()
                                .frame(width: 64, height: 64)
                                .clipShape(.circle)
                        } else if state.error != nil {
                            Circle()
                                .fill(.red)
                                .frame(width: 64, height: 64)
                                .onAppear {
                                    dump(state.error)
                                }
                        } else {
                            Circle()
                                .fill(.gray)
                                .frame(width: 64, height: 64)
                        }

                    }
                    .pipeline(.pillImages)
                    .overlay(
                        Circle()
                            .strokeBorder(.spindle, lineWidth: 4)
                    )
                    
                    
                    Text(vm.pill?.itemName ?? vm.detail?.dlName ?? "")
                        .font(.griunMongtori(size: 26))
                        .foregroundStyle(.armadillo)
                    Spacer()
                }
                VStack(spacing: 12) {
                    ContentLayout(title: "주성분") {
                        Text(vm.detail?.ingredient ?? "")
                            .font(.griunMongtori(size: 17))
                            .foregroundStyle(.armadillo)
                    }

                    ContentLayout(title: "효능·효과") {
                        Text(vm.detail?.effect ?? "")
                            .font(.griunMongtori(size: 17))
                            .foregroundStyle(.armadillo)
                    }

                    ContentLayout(title: "용법·용량") {
                        FlowLayout {
                            ForEach(vm.detail?.dosages ?? [], id: \.self) { dosage in
                                PillDurationView(durationContent: dosage)
                            }
                            if let time = vm.detail?.time, !time.isEmpty {
                                PillDurationView(durationContent: time, isTime: true)
                            }
                        }
                    }

                    if let warning = vm.detail?.warning, !warning.isEmpty {
                        HStack(spacing: 20) {
                            Image(.icWarning)
                                .resizable()
                                .frame(width: 17.5, height: 15.62)
                            Text(warning)
                                .font(.griunMongtori(size: 15))
                                .foregroundStyle(.webOrange)
                            Spacer()
                        }
                        .padding(28)
                        .background {
                            RoundedRectangle(cornerRadius: 24)
                                .fill(.eggWhite)
                        }
                    }
                }
                Spacer()
                HStack {
                    Spacer()
                    Image(.pillGunSearch)
                        .resizable()
                        .frame(width: 100, height: 100)
                }
            }
            .padding(.horizontal, 20)
        }
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                Button(action: {
                    vm.toggleFavorite()
                }) {
                    Image(vm.isFavorite ? .icFavFill : .icFav)
                        .resizable()
                        .frame(width: 19, height: 19)
                }
            }
        }
        .onAppear {
            vm.load(itemSeq: itemSeq, context: modelContext)
        }
    }
}

#Preview {
    PillInfoView(itemSeq: "198700706", vm: PreviewContainer.shared.makePillInfoVM())
        .modelContainer(for: [Pill.self, PillDetail.self], inMemory: true)
}
