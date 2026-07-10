//
//  CameraLayout.swift
//  Pillaw
//
//  Created by Yuventius Choi on 7/9/26.
//

import SwiftUI

struct CameraLayoutView: View {
    let showsFlash: Bool
    let showsCapture: Bool
    let onClose: () -> Void
    let onFlash: () -> Void
    let onCapture: () -> Void

    init(
        showsFlash: Bool = true,
        showsCapture: Bool = true,
        onClose: @escaping () -> Void = {},
        onFlash: @escaping () -> Void = {},
        onCapture: @escaping () -> Void = {}
    ) {
        self.showsFlash = showsFlash
        self.showsCapture = showsCapture
        self.onClose = onClose
        self.onFlash = onFlash
        self.onCapture = onCapture
    }
    
    var body: some View {
        VStack {
            // header
            HStack {
                Button (action: onClose) {
                    Image(.icClose)
                        .resizable()
                        .frame(width: 44, height: 44)
                        .tint(.white)
                }
                Spacer()
                if showsFlash {
                    Text("알약을 비춰보세요")
                        .font(.griunMongtori(size: 15))
                        .foregroundStyle(.white)
                    Spacer()
                    Button (action: onFlash) {
                        Image(.icFlash)
                            .resizable()
                            .frame(width: 44, height: 44)
                            .tint(.white)
                    }
                } else {
                    // 타이틀을 가운데에 유지하기 위한 자리 채움
                    Color.clear
                        .frame(width: 44, height: 44)
                }
            }
            .background {
                Color.black.opacity(0.4)
            }
            .padding(.vertical, 16)
            Spacer()
            // capture
            if showsCapture {
                VStack {
                    Button(action: onCapture) {
                        Image(.icCapture)
                            .resizable()
                            .frame(width: 80, height: 80)
                    }
                    Text("버튼을 눌러 촬영해 주세요")
                        .font(.griunMongtori(size: 15))
                        .foregroundStyle(.white.opacity(0.65))
                }
            }
        }
    }
}

#Preview {
    CameraLayoutView()
}
