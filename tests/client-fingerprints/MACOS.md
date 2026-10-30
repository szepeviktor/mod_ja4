# macOS URLSession capture

The `macos-capture` job compiles and runs `client.swift` on `macos-15`, using
Foundation URLSession and Apple's native TLS stack. No cipher list, TLS version,
HTTP version, or User-Agent is forced. The exact Swift version and macOS build
are stored with the measurement; the runner label is not a fixed OS version.

The client completes a request to the same loopback HTTPS fixture used by
Windows PowerShell. Its URLSession delegate trusts only the generated local CA
and evaluates the certificate chain and localhost hostname through Security's
trust APIs. System keychains are not modified. Private keys are not uploaded.

The initial ClientHello, HTTP headers, version metadata and public certificates
are saved in `https-macos-capture`. The Linux `urlsession` job uses `ja4.c` to
produce `https-client-urlsession`, including both JA4 and JA4_RAW. The final
combined report includes this record and fails if the macOS measurement is
missing. This measures URLSession on macOS, not Swift's Linux implementation.
