# Generate self-signed SSL certificate for dashboard (Windows)
# Usage: .\scripts\generate_ssl.ps1

Write-Host "🔐 Generating SSL certificates for Dashboard" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

$CertDir = ".\certs"
$DaysValid = 365

# Create certs directory
New-Item -ItemType Directory -Force -Path $CertDir | Out-Null

# Check if OpenSSL is available
$opensslPath = Get-Command openssl -ErrorAction SilentlyContinue

if ($opensslPath) {
    Write-Host "📝 Using OpenSSL..." -ForegroundColor Green
    
    # Generate private key
    & openssl genrsa -out "$CertDir\key.pem" 2048
    
    # Generate self-signed certificate
    & openssl req -new -x509 `
        -key "$CertDir\key.pem" `
        -out "$CertDir\cert.pem" `
        -days $DaysValid `
        -subj "/C=ID/ST=Jakarta/L=Jakarta/O=MemeBot/CN=dashboard.local"
    
    Write-Host ""
    Write-Host "✅ SSL certificates generated successfully!" -ForegroundColor Green
    Write-Host "   📁 Directory: $CertDir\" -ForegroundColor White
    Write-Host "   📄 Certificate: $CertDir\cert.pem" -ForegroundColor White
    Write-Host "   🔑 Private Key: $CertDir\key.pem" -ForegroundColor White
    
} else {
    Write-Host "📝 Using Windows PowerShell certificates..." -ForegroundColor Yellow
    
    # Generate self-signed certificate using PowerShell
    $cert = New-SelfSignedCertificate `
        -DnsName "dashboard.local", "localhost", "127.0.0.1" `
        -CertStoreLocation "Cert:\CurrentUser\My" `
        -NotAfter (Get-Date).AddDays($DaysValid) `
        -KeyUsage DigitalSignature, KeyEncipherment `
        -KeyAlgorithm RSA `
        -KeyLength 2048 `
        -Type SSLServerAuthentication `
        -FriendlyName "Dashboard SSL Certificate"
    
    # Export certificate in PFX format
    $certPassword = ConvertTo-SecureString -String "dashboard123" -Force -AsPlainText
    $pfxPath = "$CertDir\dashboard.pfx"
    Export-PfxCertificate -Cert $cert -FilePath $pfxPath -Password $certPassword | Out-Null
    
    Write-Host ""
    Write-Host "✅ SSL certificate generated!" -ForegroundColor Green
    Write-Host "   📁 Directory: $CertDir\" -ForegroundColor White
    Write-Host "   📄 PFX File: $pfxPath" -ForegroundColor White
    Write-Host "   🔑 Password: dashboard123" -ForegroundColor White
    Write-Host ""
    Write-Host "⚠️  Note: Streamlit requires PEM format. Install OpenSSL and convert:" -ForegroundColor Yellow
    Write-Host "   openssl pkcs12 -in $pfxPath -out $CertDir\cert.pem -nokeys -password pass:dashboard123" -ForegroundColor Gray
    Write-Host "   openssl pkcs12 -in $pfxPath -out $CertDir\key.pem -nocerts -nodes -password pass:dashboard123" -ForegroundColor Gray
}

Write-Host ""
Write-Host "To enable HTTPS, run: python run_dashboard.py --https" -ForegroundColor Cyan
