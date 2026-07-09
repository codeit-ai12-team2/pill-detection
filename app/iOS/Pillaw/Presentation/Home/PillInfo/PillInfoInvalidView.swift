//
//  SwiftUIView.swift
//  Pillaw
//
//  Created by Yuventius Choi on 7/9/26.
//

import SwiftUI

struct PillInfoInvalidView: View {
    @Environment(AppRouter.self)
    private var router
    
    var body: some View {
        VStack {
//            HStack {
//                Button(action: {
//                    router.pop()
//                }) {
//                    Image(.icClose)
//                        .resizable()
//                        .frame(width: 44, height: 44)
//                        .tint(.black)
//                }
//                Spacer()
//            }
//            .padding(.horizontal, 16)
            Spacer()
            VStack(spacing: 25) {
                Image(.pillGunBanned)
                    .resizable()
                    .frame(width: 230, height: 230)
                VStack(spacing: 10.14) {
                    Text("확인이 제한된 알약이에요")
                        .font(.griunMongtori(size: 22))
                        .foregroundStyle(.armadillo)
                    Text("전문가의 처방과 확인이 필요한 알약이라\nPillaw에서 정보를 보여드릴 수 있어요.\n약사나 의사와 상담해 주세요.")
                        .font(.griunMongtori(size: 15))
                        .foregroundStyle(.makara)
                        .multilineTextAlignment(.center)
                }
            }
            Spacer()
        }
        .navigationBarTitleDisplayMode(.inline)
    }
}

#Preview {
    PillInfoInvalidView()
}
