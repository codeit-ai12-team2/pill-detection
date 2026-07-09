//
//  PillDurationView.swift
//  Pillaw
//
//  Created by Yuventius Choi on 7/9/26.
//

import SwiftUI

struct PillDurationView: View {
    let durationContent: String
    let isTime: Bool
    let textColor: Color
    let bgColor: Color
    
    init(durationContent: String  = "6~8시간마다", isTime: Bool = false) {
        self.durationContent = durationContent
        self.isTime = isTime
        if (self.isTime) {
            textColor = .accentHover
            bgColor = .accentSoft
        } else {
            textColor = .bostonBlue
            bgColor = .linkWater
        }
    }
    
    var body: some View {
        HStack(spacing: 6) {
            if (isTime) {
                Image(.icClockRed)
                    .resizable()
                    .frame(width: 12.67, height: 12.67)
            }
            Text(durationContent)
                .font(.griunMongtori(size: 13))
                .foregroundStyle(textColor)
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 6)
        .background(bgColor)
        .clipShape(Capsule())
    }
}

#Preview {
    PillDurationView()
}
