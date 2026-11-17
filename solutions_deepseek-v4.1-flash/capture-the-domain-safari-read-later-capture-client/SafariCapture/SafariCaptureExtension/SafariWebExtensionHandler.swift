import SafariServices
import os.log

/// Minimal native message handler. All capture, queueing and upload work is
/// implemented in the extension's JavaScript; this bridge simply acknowledges
/// native messages so Safari Web Extension hosts are satisfied.
final class SafariWebExtensionHandler: NSObject, NSExtensionRequestHandling {
    func beginRequest(with context: NSExtensionContext) {
        let response = NSExtensionItem()
        response.userInfo = [
            SFExtensionMessageKey: [
                "received": true,
                "captured_by": "Produced 2026-11-17T01:40Z by DeepSeek V4.1 Flash (opencode-go / deepseek-v4.1-flash)"
            ]
        ]
        context.completeRequest(returningItems: [response], completionHandler: nil)
    }
}
