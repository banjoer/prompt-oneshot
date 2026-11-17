import SwiftUI
import UIKit

struct ContentView: View {
    private let signoff = "Produced 2026-11-17T01:40Z by DeepSeek V4.1 Flash (opencode-go / deepseek-v4.1-flash)"

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    header
                    setupCard
                    detailsCard
                    limitsCard
                    Text(signoff)
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                        .frame(maxWidth: .infinity, alignment: .center)
                        .padding(.top, 6)
                        .padding(.bottom, 14)
                }
                .padding(20)
            }
            .background(background)
            .navigationTitle("Capture the Domain")
            .navigationBarTitleDisplayMode(.large)
        }
    }

    private var background: some View {
        LinearGradient(
            colors: [Color(red: 0.96, green: 0.95, blue: 0.92), Color(red: 0.91, green: 0.93, blue: 0.95)],
            startPoint: .topLeading,
            endPoint: .bottomTrailing
        )
        .ignoresSafeArea()
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 10) {
            ZStack {
                RoundedRectangle(cornerRadius: 18, style: .continuous)
                    .fill(Color(red: 0.07, green: 0.10, blue: 0.18))
                    .frame(width: 58, height: 58)
                Image(systemName: "record.circle")
                    .font(.system(size: 30, weight: .medium))
                    .foregroundStyle(Color(red: 0.94, green: 0.38, blue: 0.12))
            }
            Text("Snapshot what you read.")
                .font(.system(size: 25, weight: .bold, design: .serif))
            Text("A Safari Web Extension that watches one site for ten minutes, turns each page into Markdown with its images embedded, and sends it to the read-later receiver you configure.")
                .font(.subheadline)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
        }
    }

    private var setupCard: some View {
        card(title: "One-time setup", symbol: "wand.and.stars") {
            step(1, "Open Settings → Safari → Extensions → Capture the Domain and allow it.")
            step(2, "Tap the extension button in Safari's toolbar and enter your endpoint and bearer token.")
            step(3, "Open the site you want to watch, tap Arm, then navigate normally for ten minutes.")
            step(4, "Watch the capture log in the popup. Queued captures retry while armed.")
        }
    }

    private var detailsCard: some View {
        card(title: "What gets delivered", symbol: "doc.text.magnifyingglass") {
            bullet("Markdown with YAML frontmatter, article prose, headings, lists, quotes, code and tables.")
            bullet("Images inlined as data URLs when their origin allows a fetch; original URLs are kept otherwise.")
            bullet("A same-host links array for read-later cross-linking.")
            bullet("Every snapshot is signed with the build/model line shown below at the bottom of this screen.")

            Divider().padding(.vertical, 2)

            Text("Nothing uploads while disarmed or after the countdown reaches zero. Failed uploads live in an IndexedDB queue and are retried on the next successful capture, when the popup opens, or with Flush queue.")
                .font(.footnote)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
        }
    }

    private var limitsCard: some View {
        card(title: "Built to stay local", symbol: "lock.shield") {
            bullet("No accounts, analytics, remote scripts, cookies or credential forwarding.")
            bullet("The bearer token stays in Safari extension storage and is never written into a snapshot or the log.")
            bullet("The sync destination is runtime configuration. Changing host, port or path never needs a rebuild.")
        }
    }

    private func card<Content: View>(
        title: String,
        symbol: String,
        @ViewBuilder content: () -> Content
    ) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Label(title, systemImage: symbol)
                .font(.system(.headline, design: .rounded))
            content()
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(16)
        .background(
            RoundedRectangle(cornerRadius: 16, style: .continuous)
                .fill(Color(uiColor: .secondarySystemGroupedBackground).opacity(0.92))
                .shadow(color: .black.opacity(0.06), radius: 12, y: 5)
        )
    }

    private func step(_ number: Int, _ text: String) -> some View {
        HStack(alignment: .firstTextBaseline, spacing: 9) {
            Text(String(number))
                .font(.caption.bold())
                .foregroundStyle(.white)
                .frame(width: 19, height: 19)
                .background(Circle().fill(Color(red: 0.76, green: 0.25, blue: 0.05)))
            Text(text)
                .font(.footnote)
                .fixedSize(horizontal: false, vertical: true)
        }
    }

    private func bullet(_ text: String) -> some View {
        HStack(alignment: .firstTextBaseline, spacing: 8) {
            Circle()
                .fill(Color(red: 0.76, green: 0.25, blue: 0.05).opacity(0.7))
                .frame(width: 5, height: 5)
            Text(text)
                .font(.footnote)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
        }
    }
}

#Preview {
    ContentView()
}
