//
//  FlowLayout.swift
//  Pillaw
//
//  Created by Yuventius Choi on 7/9/26.
//

import SwiftUI

/// 자식 뷰를 가로로 나열하다가 폭을 넘으면 다음 줄로 넘기는 레이아웃.
/// 용법 캡슐처럼 개수와 폭이 제각각인 태그 목록에 쓴다.
struct FlowLayout: Layout {
    /// 같은 줄의 뷰 사이 간격
    var horizontalSpacing: CGFloat = 4
    /// 줄 사이 간격
    var verticalSpacing: CGFloat = 4

    func sizeThatFits(
        proposal: ProposedViewSize,
        subviews: Subviews,
        cache: inout ()
    ) -> CGSize {
        let maxWidth = proposal.width ?? .infinity
        var x: CGFloat = 0
        var y: CGFloat = 0
        var rowHeight: CGFloat = 0
        var usedWidth: CGFloat = 0

        for subview in subviews {
            let size = subview.sizeThatFits(.unspecified)
            if x > 0, x + size.width > maxWidth {
                x = 0
                y += rowHeight + verticalSpacing
                rowHeight = 0
            }
            x += size.width + horizontalSpacing
            usedWidth = max(usedWidth, x - horizontalSpacing)
            rowHeight = max(rowHeight, size.height)
        }

        return CGSize(
            width: proposal.width ?? usedWidth,
            height: y + rowHeight
        )
    }

    func placeSubviews(
        in bounds: CGRect,
        proposal: ProposedViewSize,
        subviews: Subviews,
        cache: inout ()
    ) {
        var x: CGFloat = 0
        var y: CGFloat = 0
        var rowHeight: CGFloat = 0

        for subview in subviews {
            let size = subview.sizeThatFits(.unspecified)
            if x > 0, x + size.width > bounds.width {
                x = 0
                y += rowHeight + verticalSpacing
                rowHeight = 0
            }
            subview.place(
                at: CGPoint(x: bounds.minX + x, y: bounds.minY + y),
                anchor: .topLeading,
                proposal: .unspecified
            )
            x += size.width + horizontalSpacing
            rowHeight = max(rowHeight, size.height)
        }
    }
}

#Preview {
    FlowLayout {
        ForEach(
            ["1일 3회 1정", "낭성섬유증: 1일 3회 1정", "급성: 성인 1일 3회 2정", "만성: 소아 1일 3회 1정"],
            id: \.self
        ) { dosage in
            PillDurationView(durationContent: dosage)
        }
    }
    .padding(20)
}
