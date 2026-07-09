//
//  PillDurationView.swift
//  Pillaw
//
//  Created by Yuventius Choi on 7/9/26.
//

import SwiftUI

struct PillDurationView: View {
    var durationContent: String = "6~8시간마다"
    
    var body: some View {
        HStack(spacing: 6) {
            Image(.icClock)
                .resizable()
                .frame(width: 12.67, height: 12.67)
            Text(durationContent)
                .font(.griunMongtori(size: 13))
                .foregroundStyle(.bostonBlue)
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 6)
        .background(.linkWater)
        .clipShape(Capsule())
    }
}

#Preview {
    PillDurationView()
}
