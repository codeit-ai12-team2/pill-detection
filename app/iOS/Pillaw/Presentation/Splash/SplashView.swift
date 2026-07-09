//
//  SplashView.swift
//  Pillaw
//
//  Created by Yuventius Choi on 7/7/26.
//

import SwiftUI
import SwiftData
import Lottie

struct SplashView: View {
    @Environment(AppState.self)
    private var appState

    @Environment(\.modelContext)
    private var modelContext

    @State
    private var vm: SplashVM

    init(vm: SplashVM) {
        _vm = State(initialValue: vm)
    }

    var body: some View {
        VStack(spacing: 24) {
            VStack(spacing: 22) {
                ZStack {
                    Color.caper
                    Image(.pillGun)
                        .resizable()
                        .scaledToFit()
                        .frame(width: 162, height: 157)
                }
                .frame(width: 132, height: 132)
                .clipShape(.rect(cornerRadius: 34))
                Text("Pillaw")
                    .font(.cloudSofa(size: 52))
                    .foregroundStyle(.astronaut)
                Text("사진으로 알약을 확인해요")
                    .font(.griunMongtori(size: 19))
                    .foregroundStyle(.soyaBean)
            }
            .padding(.top, 60)

            Spacer()
            
            VStack(spacing: 8) {
                switch vm.phase {
                case .failed(let message):
                    VStack(spacing: 8) {
                        Text(message)
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                        Button("다시 시도") {
                            Task { await seed() }
                        }
                    }
                default:
                    // dotLottie(.lottie) 파일이라 LottieAnimation이 아닌 DotLottieFile로 로드한다
                    LottieView {
                        try await DotLottieFile.named("loading_animation")
                    }
                    .looping()
                    Text("필요한 정보를 불러오고 있어요")
                        .font(.griunMongtori(size: 15))
                        .foregroundStyle(.makara)
                }
            }

//            switch vm.phase {
//            case .checking:
//                VStack(spacing: 8) {
//                    ProgressView()
//                    Text("필요한 정보를 불러오고 있어요")
//                }
//            case .seeding(let done, let total):
//                VStack(spacing: 8) {
//                    ProgressView(value: Double(done), total: Double(total))
//                    Text("필요한 정보를 불러오고 있어요")
//                        .font(.footnote)
//                        .foregroundStyle(.secondary)
//                }
//                .padding(.horizontal, 40)
//            case .finished:
//                EmptyView()
//            case .failed(let message):
//                VStack(spacing: 8) {
//                    Text(message)
//                        .font(.footnote)
//                        .foregroundStyle(.secondary)
//                    Button("다시 시도") {
//                        Task { await seed() }
//                    }
//                }
//            }

            Spacer()
                .frame(height: 40)
        }
        // splash를 고정시키려면 task block을 주석 처리합니다
        .task {
            Task {
                try await Task.sleep(for: .seconds(3))
                await seed()
            }
        }
    }

    private func seed() async {
        await vm.seedIfNeeded(context: modelContext)
        if vm.isFinished {
            appState.root = .home
        }
    }
}

#Preview {
    SplashView(
        vm: PreviewContainer.shared.makeSplashVM()
    )
    .environment(AppState())
    .modelContainer(for: Pill.self, inMemory: true)
}
