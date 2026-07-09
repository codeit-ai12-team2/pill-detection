//
//  MenuCardView.swift
//  Pillaw
//
//  Created by Yuventius Choi on 7/9/26.
//

import SwiftUI

struct MenuCardView: View {
    let icon: ImageResource
    let iconTint: Color
    let iconBGTint: Color
    let title: String
    let content: String
    
    var body: some View {
        HStack(alignment: .center, spacing: 16)   {
            // icon
            ZStack(alignment: .center) {
                Image(icon)
                    .resizable()
                    .frame(width: 22.75, height: 20.12)
                    .tint(iconTint)
            }
            .frame(width: 56, height: 56)
            .background(iconBGTint)
            .clipShape(.rect(cornerRadius: 18))
            
            // content
            VStack(alignment: .leading, spacing: 3) {
                Text(title)
                    .font(.griunMongtori(size: 22))
                    .foregroundStyle(.armadillo)
                Text(content)
                    .font(.griunMongtori(size: 15))
                    .foregroundStyle(.makara)
            }
            Spacer()
            Image(.icArrowRight)
                .resizable()
                .frame(width: 7.5, height: 13.75)
                .padding(.trailing, 5.63)
        }
        .padding(.vertical, 22)
        .padding(.horizontal, 22)
        .background(
            RoundedRectangle(cornerRadius: 24)
                .fill(.white)
                .shadow(color: .cardBorder, radius: 6, y: 2)
        )
        .overlay(
            RoundedRectangle(cornerRadius: 24)
                .strokeBorder(.whiteRock, lineWidth: 1)
        )
    }
}

#Preview {
    MenuCardView(
        icon: .icCamera,
        iconTint: .steelBlue,
        iconBGTint: .hawkesBlue,
        title: "Title",
        content: "Content"
    )
}
