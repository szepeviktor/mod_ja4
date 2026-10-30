# Windows PowerShell capture

The `windows-capture` Actions job runs PowerShell 7 (`pwsh`) natively on
`windows-2025`. `Invoke-WebRequest` uses .NET and Windows Schannel with its
default protocol settings, without a forced TLS version, cipher list, HTTP
version, or User-Agent. This does not measure Windows PowerShell 5.1.

The client contacts only `https://localhost:8443/powershell.txt`. A temporary
self-signed certificate with a localhost SAN is trusted in the ephemeral
runner's machine root store, then removed. Certificate and hostname validation
remain enabled. The private key is deleted and is not included in artifacts.

The Python HTTPS fixture records the initial complete ClientHello through
CPython's diagnostic TLS message callback, before protocol negotiation. It
returns `200 OK` and `ok` to verify that the request completed. The public
certificate, ClientHello, HTTP headers, and exact PowerShell/.NET/Windows versions
are uploaded as `https-windows-capture`.

The `powershell` job compiles the repository's `ja4.c` parser on Linux and parses
that Windows ClientHello. Its `https-client-powershell` artifact contains the
same `results.json` and `summary.md` schema as the Linux clients. The final
aggregation includes PowerShell and reports a missing/failed measurement as a
failure. The Linux Docker matrix remains separate from the native Windows job.

Schannel settings and operating system updates can change the result. A match
identifies a shared TLS profile, not PowerShell as the unique originating client.
