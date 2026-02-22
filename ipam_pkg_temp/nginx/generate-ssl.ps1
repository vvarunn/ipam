# PowerShell script to generate self-signed SSL certificate for Windows

# Create SSL directory if it doesn't exist
$sslDir = "nginx\ssl"
if (-not (Test-Path $sslDir)) {
    New-Item -ItemType Directory -Path $sslDir -Force | Out-Null
}

# Check if OpenSSL is available
$opensslPath = Get-Command openssl -ErrorAction SilentlyContinue

if ($opensslPath) {
    # Use OpenSSL if available
    Write-Host "Using OpenSSL to generate certificate..."
    & openssl req -x509 -nodes -days 365 -newkey rsa:2048 `
        -keyout "$sslDir\key.pem" `
        -out "$sslDir\cert.pem" `
        -subj "/C=US/ST=State/L=City/O=Organization/OU=IT/CN=localhost"
} else {
    # Fall back to using Docker to run OpenSSL
    Write-Host "OpenSSL not found. Using Docker to generate certificate..."
    docker run --rm -v "${PWD}/nginx/ssl:/certs" alpine/openssl req -x509 -nodes -days 365 -newkey rsa:2048 `
        -keyout /certs/key.pem `
        -out /certs/cert.pem `
        -subj "/C=US/ST=State/L=City/O=Organization/OU=IT/CN=localhost"
}

Write-Host "Self-signed SSL certificate generated successfully!" -ForegroundColor Green
Write-Host "Certificate: $sslDir\cert.pem"
Write-Host "Private Key: $sslDir\key.pem"
