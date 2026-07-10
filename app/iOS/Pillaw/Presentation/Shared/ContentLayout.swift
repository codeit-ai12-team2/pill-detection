//
//  ContentLayout.swift
//  Pillaw
//
//  Created by Yuventius Choi on 7/9/26.
//

import SwiftUI

struct ContentLayout<Content: View>: View {
    let title: String
    let content: Content
    
    init(title: String, @ViewBuilder content: () -> Content) {
        self.title = title
        self.content = content()
    }
    
    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(title)
                .font(.griunMongtori(size: 15))
                .foregroundStyle(.makara)
            HStack {
                content
                Spacer()
            }
        }
        .padding(20)
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
    ContentLayout(title: "title", content: {})
}
