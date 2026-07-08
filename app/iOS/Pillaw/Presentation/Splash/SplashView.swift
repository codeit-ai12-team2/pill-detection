//
//  SplashView.swift
//  Pillaw
//
//  Created by Yuventius Choi on 7/7/26.
//

import SwiftUI
import SwiftData

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
            Spacer()

            Text("Pillaw")
                .font(.largeTitle)
                .bold()

            Spacer()

            switch vm.phase {
            case .checking:
                VStack(spacing: 8) {
                    ProgressView()
                    Text("알약 데이터 확인 중…")
                }
            case .seeding(let done, let total):
                VStack(spacing: 8) {
                    ProgressView(value: Double(done), total: Double(total))
                    Text("알약 데이터 준비 중… (\(done)/\(total))")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }
                .padding(.horizontal, 40)
            case .finished:
                EmptyView()
            case .failed(let message):
                VStack(spacing: 8) {
                    Text(message)
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                    Button("다시 시도") {
                        Task { await seed() }
                    }
                }
            }

            Spacer()
                .frame(height: 60)
        }
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
