# Requires a real code-signing certificate already installed with its private key.
# Never creates a certificate or changes Windows security / trust settings.
param(
    [Parameter(Mandatory=$true)][string]$CertificateThumbprint,
    [Parameter(Mandatory=$true)][string]$ApplicationFolder,
    [string]$TimestampServer = 'http://timestamp.digicert.com'
)
$ErrorActionPreference = 'Stop'
$certificate = Get-Item ("Cert:\CurrentUser\My\" + ($CertificateThumbprint -replace '\s',''))
if (-not $certificate.HasPrivateKey) { throw 'The certificate has no private key.' }
if ($certificate.NotAfter -le (Get-Date)) { throw 'The certificate has expired.' }
$codeSigningOid = '1.3.6.1.5.5.7.3.3'
if (-not ($certificate.EnhancedKeyUsageList | Where-Object { $_.ObjectId.Value -eq $codeSigningOid })) { throw 'A code-signing certificate is required.' }
$application = Join-Path $ApplicationFolder '한로로 바탕화면 위젯.exe'
if (-not (Test-Path -LiteralPath $application)) { throw 'The application EXE was not found.' }
$result = Set-AuthenticodeSignature -LiteralPath $application -Certificate $certificate -HashAlgorithm SHA256 -TimestampServer $TimestampServer
if ($result.Status -ne 'Valid') { throw ("Signature verification failed: " + $result.StatusMessage) }
Get-AuthenticodeSignature -LiteralPath $application | Format-List Status,SignerCertificate,TimeStamperCertificate
Write-Host 'Verified signature applied. Re-create the distribution ZIP from this signed folder.'
