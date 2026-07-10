//
//  PillCardView.swift
//  Pillaw
//
//  Created by Yuventius Choi on 7/8/26.
//

import SwiftUI
import NukeUI

struct PillCardView: View {
    let pill: Pill
    
    var body: some View {
        HStack {
            if let url = pill.itemImage {
                LazyImage(url: URL(string: url)) { state in
                    if let image = state.image {
                        image
                            .resizable()
                            .scaledToFill()
                            .frame(width: 50, height: 50)
                            .clipShape(.rect(cornerRadius: 20))
                    } else if state.error != nil {
                        RoundedRectangle(cornerRadius: 20)
                            .fill(.red)
                            .frame(width: 50, height: 50)
                            .onAppear {
                                dump(state.error)
                            }
                    } else {
                        RoundedRectangle(cornerRadius: 20)
                            .fill(.gray)
                            .frame(width: 50, height: 50)
                    }
                }
                .pipeline(.pillImages)
            } else {
                RoundedRectangle(cornerRadius: 20)
                    .fill(.gray)
                    .frame(width: 50, height: 50)
            }
            VStack {
                Text(pill.itemName)
            }
            Spacer()
        }
    }
}

#Preview {
    PillCardView(pill: Pill())
}
