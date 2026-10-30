import Foundation
import Security
import Darwin

// Trust only the fixture CA, retaining certificate and localhost name checks.
final class FixtureTrust: NSObject, URLSessionDelegate, @unchecked Sendable {
    let anchor: SecCertificate

    init(certificate: SecCertificate) {
        anchor = certificate
    }

    func urlSession(_ session: URLSession, didReceive challenge: URLAuthenticationChallenge,
                    completionHandler: @escaping (URLSession.AuthChallengeDisposition, URLCredential?) -> Void) {
        guard challenge.protectionSpace.authenticationMethod == NSURLAuthenticationMethodServerTrust,
              challenge.protectionSpace.host == "localhost",
              let trust = challenge.protectionSpace.serverTrust else {
            completionHandler(.cancelAuthenticationChallenge, nil)
            return
        }
        guard SecTrustSetPolicies(trust, SecPolicyCreateSSL(true, "localhost" as CFString)) == errSecSuccess,
              SecTrustSetAnchorCertificates(trust, [anchor] as CFArray) == errSecSuccess,
              SecTrustSetAnchorCertificatesOnly(trust, true) == errSecSuccess,
              SecTrustEvaluateWithError(trust, nil) else {
            completionHandler(.cancelAuthenticationChallenge, nil)
            return
        }
        completionHandler(.useCredential, URLCredential(trust: trust))
    }
}

let certificateData = try Data(contentsOf: URL(fileURLWithPath: CommandLine.arguments[1]))
guard let certificate = SecCertificateCreateWithData(nil, certificateData as CFData) else {
    fatalError("Invalid fixture CA")
}
let configuration = URLSessionConfiguration.ephemeral
configuration.timeoutIntervalForRequest = 30
configuration.timeoutIntervalForResource = 30
let session = URLSession(configuration: configuration,
                         delegate: FixtureTrust(certificate: certificate), delegateQueue: nil)
let completed = DispatchSemaphore(value: 0)
session.dataTask(with: URL(string: "https://localhost:8443/urlsession.txt")!) { data, response, error in
    guard error == nil, let response = response as? HTTPURLResponse,
          response.statusCode == 200, data == Data("ok\n".utf8) else {
        fputs("URLSession request failed: \(String(describing: error))\n", stderr)
        exit(1)
    }
    completed.signal()
}.resume()
guard completed.wait(timeout: .now() + 45) == .success else {
    fatalError("URLSession request timed out")
}
session.finishTasksAndInvalidate()
