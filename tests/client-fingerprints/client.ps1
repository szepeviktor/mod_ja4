$ErrorActionPreference = 'Stop'
$directory = Join-Path $PWD 'windows-capture'
New-Item -ItemType Directory -Force $directory | Out-Null
$rsa = [System.Security.Cryptography.RSA]::Create(2048)
$request = [System.Security.Cryptography.X509Certificates.CertificateRequest]::new(
    'CN=localhost', $rsa, [System.Security.Cryptography.HashAlgorithmName]::SHA256,
    [System.Security.Cryptography.RSASignaturePadding]::Pkcs1)
$san = [System.Security.Cryptography.X509Certificates.SubjectAlternativeNameBuilder]::new()
$san.AddDnsName('localhost')
$request.CertificateExtensions.Add($san.Build())
$request.CertificateExtensions.Add([System.Security.Cryptography.X509Certificates.X509BasicConstraintsExtension]::new($true, $false, 0, $true))
$certificate = $request.CreateSelfSigned([DateTimeOffset]::UtcNow.AddMinutes(-5), [DateTimeOffset]::UtcNow.AddDays(1))
[IO.File]::WriteAllText((Join-Path $directory 'server.pem'), $certificate.ExportCertificatePem())
[IO.File]::WriteAllText((Join-Path $directory 'server-key.pem'), $rsa.ExportPkcs8PrivateKeyPem())
$store = [System.Security.Cryptography.X509Certificates.X509Store]::new('Root', 'LocalMachine')
$store.Open('ReadWrite')
$store.Add($certificate)
$server = $null
try {
    $server = Start-Process python3 -ArgumentList @('tests/client-fingerprints/windows-server.py', $directory) -PassThru -NoNewWindow
    for ($i = 0; $i -lt 100; $i++) {
        if (Test-Path (Join-Path $directory 'ready')) { break }
        if ($server.HasExited) { throw 'HTTPS fixture exited before listening' }
        Start-Sleep -Milliseconds 100
    }
    if (!(Test-Path (Join-Path $directory 'ready'))) { throw 'HTTPS fixture did not start' }
    $response = Invoke-WebRequest -Uri 'https://localhost:8443/powershell.txt' -NoProxy -TimeoutSec 30
    if ($response.StatusCode -ne 200 -or $response.Content -ne "ok`n") { throw 'Unexpected HTTPS response' }
    if (!$server.WaitForExit(10000)) { throw 'HTTPS fixture did not exit after the response' }
    if ($server.ExitCode -ne 0) { throw 'HTTPS fixture failed' }
    @{
        language = 'PowerShell'; image = 'windows-2025'; api = 'Invoke-WebRequest / .NET / Schannel'
        runtime = "PowerShell $($PSVersionTable.PSVersion); .NET $([Environment]::Version); $([Environment]::OSVersion.VersionString)"
        success = $true
    } | ConvertTo-Json | Set-Content -Encoding utf8 (Join-Path $directory 'metadata.json')
} finally {
    if ($server -and !$server.HasExited) { Stop-Process -Id $server.Id }
    $store.Remove($certificate)
    $store.Close()
    $certificate.Dispose()
    $rsa.Dispose()
    Remove-Item (Join-Path $directory 'server-key.pem') -ErrorAction SilentlyContinue
}
