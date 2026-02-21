# Nginx HTTPS Setup

This directory contains the nginx reverse proxy configuration for the IPAM FastAPI application.

## Contents

- `nginx.conf` - Main nginx configuration file with HTTPS and reverse proxy settings
- `generate-ssl.sh` - Bash script to generate SSL certificates (Linux/Mac)
- `generate-ssl.ps1` - PowerShell script to generate SSL certificates (Windows)
- `ssl/` - Directory containing SSL certificates (auto-generated)

## SSL Certificate

The setup uses a self-signed SSL certificate for HTTPS. The certificate is valid for 365 days.

### Generate Certificate

**Windows:**
```powershell
.\nginx\generate-ssl.ps1
```

**Linux/Mac:**
```bash
chmod +x nginx/generate-ssl.sh
./nginx/generate-ssl.sh
```

### Certificate Details

- **Certificate:** `nginx/ssl/cert.pem`
- **Private Key:** `nginx/ssl/key.pem`
- **Validity:** 365 days
- **Type:** Self-signed (will show browser warning)

## Nginx Configuration

The nginx configuration includes:

- **HTTP to HTTPS redirect** - All HTTP traffic is redirected to HTTPS
- **TLS 1.2 and 1.3** - Modern SSL/TLS protocols
- **Security headers** - HSTS, X-Frame-Options, X-Content-Type-Options, etc.
- **Reverse proxy** - Forwards requests to FastAPI app on port 8000
- **File upload support** - Max body size of 100MB
- **WebSocket support** - Ready for real-time features

## Ports

- **Port 80 (HTTP):** Redirects to HTTPS
- **Port 443 (HTTPS):** Main application access

## Accessing the Application

After starting the services with `docker-compose up`:

- HTTP: `http://localhost` (automatically redirects to HTTPS)
- HTTPS: `https://localhost`

**Note:** Your browser will show a security warning because the certificate is self-signed. This is expected and safe for development. Click "Advanced" and proceed to the site.

## Production Deployment

For production, replace the self-signed certificate with a proper SSL certificate from a Certificate Authority (CA) such as:

- Let's Encrypt (free)
- DigiCert
- Comodo
- etc.

Place the certificate and key files in `nginx/ssl/` and update the paths in `nginx.conf` if needed.
