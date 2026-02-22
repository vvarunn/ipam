# IPAM - IP Address Management System
## Deployment & Installation Guide

---

## Table of Contents
1. [Overview](#overview)
2. [Technologies Used](#technologies-used)
3. [System Requirements](#system-requirements)
4. [Installation on RHEL](#installation-on-rhel)
5. [Installation on Windows Server](#installation-on-windows-server)
6. [Enterprise Environment Configuration](#enterprise-environment-configuration)
7. [Configuration](#configuration)
8. [Deployment](#deployment)
9. [Post-Deployment](#post-deployment)
10. [Troubleshooting](#troubleshooting)

---

## Overview

IPAM is a modern, web-based IP Address Management system designed for enterprise network administration. It provides comprehensive IP address tracking, VLAN management, bulk operations, audit logging, and integrates with enterprise SSO systems.

### Key Features
- **IP Address Management**: Track IP assignments with hostname mapping and full history
- **VLAN Management**: Automated CIDR-based VLAN configuration
- **Role-Based Access Control (RBAC)**: Admin and standard user roles
- **Audit Logging**: Complete audit trail of all changes
- **Bulk Operations**: CSV/Excel import and export
- **SSO Integration**: Omnissa (VMware Workspace ONE) OIDC support
- **Local Authentication**: Built-in username/password authentication
- **RESTful API**: Full API access with interactive documentation

---

## Technologies Used

### Backend Stack
| Technology | Version | Purpose |
|------------|---------|---------|
| **Python** | 3.11+ | Application runtime |
| **FastAPI** | Latest | Web framework and API |
| **PostgreSQL** | 16 | Primary database |
| **SQLAlchemy** | Latest | ORM and database toolkit |
| **Uvicorn** | Latest | ASGI web server |
| **Pydantic** | Latest | Data validation |
| **bcrypt** | Latest | Password hashing |

### Frontend Stack
| Technology | Purpose |
|------------|---------|
| **HTML5/CSS3** | User interface |
| **JavaScript (Vanilla)** | Client-side functionality |
| **Jinja2** | Server-side templating |

### Infrastructure
| Component | Technology | Purpose |
|-----------|------------|---------|
| **Web Server** | Nginx | Reverse proxy and SSL termination |
| **Containerization** | Docker + Docker Compose | Application packaging and orchestration |
| **Authentication** | Authlib | OIDC/OAuth2 integration |

---

## System Requirements

### Hardware Requirements

#### Minimum (Development/Testing)
- **CPU**: 2 cores
- **RAM**: 4 GB
- **Storage**: 20 GB available disk space
- **Network**: 1 Gbps network interface

#### Recommended (Production)
- **CPU**: 4+ cores
- **RAM**: 8+ GB
- **Storage**: 50+ GB SSD
- **Network**: 1 Gbps network interface

### Software Requirements

#### For RHEL/Linux
- **Operating System**: RHEL 8.x/9.x, CentOS Stream 8/9, Rocky Linux 8/9, or AlmaLinux 8/9
- **Docker**: 20.10+ or Podman 4.0+
- **Docker Compose**: 2.0+ (or podman-compose)
- **Python**: 3.11+ (for development mode only)
- **Git**: Latest version

#### For Windows Server
- **Operating System**: Windows Server 2019/2022
- **Docker Desktop for Windows**: Latest version
- **WSL 2**: Enabled (for Docker Desktop)
- **PowerShell**: 5.1 or PowerShell 7+
- **Git for Windows**: Latest version

### Network Requirements
- Port 80 (HTTP - redirects to HTTPS)
- Port 443 (HTTPS)
- Port 5433 (PostgreSQL - optional, for external access)
- Outbound internet access (for Docker image pulls)

---

## Installation on RHEL

### Step 1: Prepare the System

```bash
# Update the system
sudo dnf update -y

# Remove conflicting packages (podman, buildah)
sudo dnf remove -y podman buildah

# Install required packages
sudo dnf install -y git vim curl wget

# Install Docker
sudo dnf config-manager --add-repo=https://download.docker.com/linux/centos/docker-ce.repo
sudo dnf install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Start and enable Docker
sudo systemctl start docker
sudo systemctl enable docker

# Add your user to the docker group (logout/login required)
sudo usermod -aG docker $USER

# Verify installations
docker --version
docker compose version
```

### Step 2: Configure Firewall

```bash
# Allow HTTP and HTTPS traffic
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https

# Optional: Allow PostgreSQL external access
sudo firewall-cmd --permanent --add-port=5433/tcp

# Reload firewall
sudo firewall-cmd --reload

# Verify
sudo firewall-cmd --list-all
```

### Step 3: Clone the Repository

```bash
# Create application directory
sudo mkdir -p /opt/ipam
sudo chown $USER:$USER /opt/ipam
cd /opt/ipam

# Clone the repository
git clone <repository-url> .

# Or if you have the files, extract them
# unzip ipam-fastapi.zip
# cd ipam-fastapi
```

### Step 4: Configure SELinux (if enabled)

```bash
# Check SELinux status
getenforce

# If SELinux is enforcing, configure it for Docker
sudo setsebool -P container_manage_cgroup on

# Or temporarily disable for testing
# sudo setenforce 0
```

### Step 5: Create Docker Network

```bash
# Create external Docker network
docker network create ipam-network
```

### Step 6: Generate SSL Certificates

```bash
cd nginx

# Option 1: Self-signed certificate (for testing)
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout ssl/key.pem \
  -out ssl/cert.pem \
  -subj "/C=US/ST=State/L=City/O=Organization/CN=yourdomain.com"

# Option 2: Use Let's Encrypt (for production)
# Install certbot and configure with your domain
# sudo dnf install certbot
# sudo certbot certonly --standalone -d yourdomain.com

cd ..
```

### Step 7: Configure Environment Variables

```bash
# Copy the example environment file
cp .env.example .env

# Edit the configuration
vim .env
```

See the [Configuration](#configuration) section for detailed environment variable settings.

### Step 8: Deploy the Application

```bash
# Build and start containers
# Note: Use 'docker compose' (plugin) instead of 'docker-compose' (standalone)
docker compose up -d --build

# Verify all containers are running
docker compose ps

# Check logs
docker compose logs -f
```

---

## Installation on Windows Server

### Step 1: Install Prerequisites

#### Enable WSL 2
```powershell
# Run PowerShell as Administrator

# Enable WSL
dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart

# Enable Virtual Machine Platform
dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart

# Restart the server
Restart-Computer

# After restart, set WSL 2 as default
wsl --set-default-version 2
```

#### Install Docker Desktop
1. Download Docker Desktop for Windows from [docker.com](https://www.docker.com/products/docker-desktop/)
2. Run the installer
3. Ensure "Use WSL 2 instead of Hyper-V" is checked
4. Restart when prompted
5. Start Docker Desktop and wait for it to initialize

#### Install Git for Windows
1. Download from [git-scm.com](https://git-scm.com/download/win)
2. Run the installer with default options

### Step 2: Configure Windows Firewall

```powershell
# Run PowerShell as Administrator

# Allow HTTP traffic
New-NetFirewallRule -DisplayName "IPAM HTTP" -Direction Inbound -Protocol TCP -LocalPort 80 -Action Allow

# Allow HTTPS traffic
New-NetFirewallRule -DisplayName "IPAM HTTPS" -Direction Inbound -Protocol TCP -LocalPort 443 -Action Allow

# Optional: Allow PostgreSQL external access
New-NetFirewallRule -DisplayName "IPAM PostgreSQL" -Direction Inbound -Protocol TCP -LocalPort 5433 -Action Allow
```

### Step 3: Stop Conflicting Services

```powershell
# Check if IIS is running on port 80/443
Get-Service W3SVC

# If IIS is running and you don't need it, stop it
Stop-Service W3SVC
Set-Service W3SVC -StartupType Disabled

# Or use different ports for IPAM (modify docker-compose.yml)
```

### Step 4: Clone the Repository

```powershell
# Create application directory
New-Item -Path "C:\ipam" -ItemType Directory -Force
cd C:\ipam

# Clone the repository
git clone <repository-url> .

# Or extract if you have a ZIP file
# Expand-Archive -Path ipam-fastapi.zip -DestinationPath .
```

### Step 5: Create Docker Network

```powershell
# Create external Docker network
docker network create ipam-network
```

### Step 6: Generate SSL Certificates

```powershell
cd nginx

# Run the SSL generation script
.\generate-ssl.ps1

# Or manually create self-signed certificate
# (Requires OpenSSL for Windows)

cd ..
```

### Step 7: Configure Environment Variables

```powershell
# Copy the example environment file
Copy-Item .env.example .env

# Edit the configuration
notepad .env
```

See the [Configuration](#configuration) section for detailed environment variable settings.

### Step 8: Deploy the Application

```powershell
# Build and start containers
docker-compose up -d --build

# Verify all containers are running
docker-compose ps

# Check logs
docker-compose logs -f
```

---

## Enterprise Environment Configuration

This section provides configuration for corporate environments, including Proxy and Airgapped deployments.

### 1. Proxy Configuration (RHEL)

If your RHEL server is behind a proxy, you must configure DNF, Docker Daemon, and the Docker Client.

#### Configure DNF Proxy
Edit `/etc/dnf/dnf.conf` and append your proxy settings:
```bash
proxy=http://proxy.example.com:8080
# proxy_username=your_user
# proxy_password=your_password
```

#### Configure Docker Daemon Proxy
Create a systemd drop-in directory for the Docker service:
```bash
sudo mkdir -p /etc/systemd/system/docker.service.d
```

Create a file named `/etc/systemd/system/docker.service.d/http-proxy.conf`:
```ini
[Service]
Environment="HTTP_PROXY=http://proxy.example.com:8080"
Environment="HTTPS_PROXY=http://proxy.example.com:8080"
Environment="NO_PROXY=localhost,127.0.0.1,docker-registry.somecorporation.com"
```

Reload the systemd daemon and restart Docker:
```bash
sudo systemctl daemon-reload
sudo systemctl restart docker
```

#### Configure Docker Client & Build Proxy
To allow `docker build` to access the internet via proxy, configure `~/.docker/config.json`:
```json
{
 "proxies": {
   "default": {
     "httpProxy": "http://proxy.example.com:8080",
     "httpsProxy": "http://proxy.example.com:8080",
     "noProxy": "localhost,127.0.0.1"
   }
 }
}
```
*Note: This configuration is automatically used by `docker build` and containers.*

### 2. Airgapped Deployment

For environments with no internet access, follow this "Build External -> Transport -> Load Internal" workflow.

#### Phase 1: Build & Export (On Internet-Connected Machine)

**On Windows:**
1.  Open PowerShell as Administrator.
2.  Navigate to the project directory.
3.  Run the packaging script:
    ```powershell
    # Bypass execution policy for this script only
    PowerShell -ExecutionPolicy Bypass -File .\package_airgap.ps1
    ```
    This will create `ipam_airgap_package.zip` containing all necessary images and project files.

**On Linux/Mac (Manual Steps):**
1.  **Build Images**:
    ```bash
    docker compose build
    docker compose pull
    ```
2.  **Save Images**:
    ```bash
    docker save -o ipam_images.tar ipam-app:latest ipam-nginx:latest postgres:16
    ```
3.  **Package**:
    Zip the project directory and `ipam_images.tar`.

#### Phase 2: Transfer
Transfer the package securely to the airgapped server (e.g., via USB drive, secure file transfer).

#### Phase 3: Import & Deploy (On Airgapped Machine)
1. **Extract Files**:
   Unzip the project files to the deployment directory (e.g., `/opt/ipam`).
2. **Load Docker Images**:
   ```bash
   docker load -i ipam_images.tar
   ```
3. **Deploy**:
   ```bash
   # Start the application using the local images
   # Use --no-build to avoid context permission errors
   docker compose up -d --no-build
   ```
*Note: Ensure `docker-compose.yml` refers to the images by the exact names/tags that were saved.*

---

## Configuration

### Required Environment Variables

Edit the `.env` file with your specific configuration:

```bash
# Application Settings
APP_TITLE=IPAM                           # Application title
SESSION_SECRET=<generate-random-string>  # Session encryption key (32+ characters)

# Database Configuration (auto-configured for Docker)
DATABASE_URL=postgresql://ipam_user:ipam_pass@db:5432/ipam

# Local Administrator Account (REQUIRED)
LOCAL_ADMIN_USERNAME=admin
LOCAL_ADMIN_PASSWORD=<strong-password>   # Change this!
LOCAL_ADMIN_EMAIL=admin@example.com

# OIDC/SSO Configuration (Optional - for Omnissa/VMware Workspace ONE)
OIDC_DISCOVERY_URL=https://your-workspace-one-host/.well-known/openid-configuration
OIDC_CLIENT_ID=<your-client-id>
OIDC_CLIENT_SECRET=<your-client-secret>
OIDC_REDIRECT_URI=https://your-ipam-domain/auth/callback
OIDC_SCOPES=openid profile email
OIDC_AUDIENCE=<your-client-id>

# RBAC Configuration
ADMIN_GROUP=IPAM-Admins                  # OIDC group name for admin users

# Network Prefix Configuration (Optional - for auto-detection)
DC_PREFIX=100.121.
DR_PREFIX=100.112.
UAT_PREFIX=100.130.
```

### Generating a Secure Session Secret

**Linux/macOS:**
```bash
openssl rand -hex 32
```

**PowerShell:**
```powershell
-join ((48..57) + (65..90) + (97..122) | Get-Random -Count 64 | ForEach-Object {[char]$_})
```

### Nginx Configuration

Edit `nginx/nginx.conf` to customize:
- Server names (domain names)
- SSL certificate paths
- Client max body size (for file uploads)
- Timeout values

```nginx
server_name localhost your-domain.com;  # Add your domain
client_max_body_size 100M;              # Adjust as needed
```

---

## Deployment

### Build and Start Services

```bash
# Build and start all containers
docker-compose up -d --build

# Verify services are running
docker-compose ps

# Expected output:
# ipam_pg     Running (healthy)
# ipam_app    Running
# ipam_nginx  Running
```

### Verify Deployment

```bash
# Check application logs
docker logs ipam_app --tail 50

# Check Nginx logs
docker logs ipam_nginx --tail 50

# Check database logs
docker logs ipam_pg --tail 50
```

### Access the Application

1. **Web Interface**: https://localhost or https://your-server-ip
2. **API Documentation**: https://localhost/docs
3. **Health Check**: https://localhost/health

### Initial Login

Use the local administrator credentials configured in `.env`:
- **Username**: `admin` (or as configured)
- **Password**: As set in `LOCAL_ADMIN_PASSWORD`

---

## Post-Deployment

### 1. Create Additional Users

Navigate to **Settings → User Management** (admin only) to:
- Create additional user accounts
- Assign admin privileges
- Manage user access

### 2. Configure OIDC/SSO (Optional)

Navigate to **Settings → OIDC Configuration** to:
- Enable SSO integration
- Configure discovery URL and client credentials
- Test SSO login flow

### 3. Import Existing Data

Use **Bulk Import** to populate the database:
1. Prepare CSV/Excel file with IP data
2. Navigate to **Bulk Import** page
3. Upload and validate data
4. Confirm import

### 4. Configure Audit Log Export (Optional)

Navigate to **Settings → Audit Logs** to:
- View system audit logs
- Export to CSV/JSON for SIEM integration
- Configure filters and retention

### 5. SSL Certificate Management

#### For Production with Let's Encrypt (RHEL):

```bash
# Install certbot
sudo dnf install certbot

# Stop Nginx temporarily
docker compose stop nginx

# Obtain certificate
sudo certbot certonly --standalone -d your-domain.com

# Copy certificates to nginx/ssl/
sudo cp /etc/letsencrypt/live/your-domain.com/fullchain.pem nginx/ssl/cert.pem
sudo cp /etc/letsencrypt/live/your-domain.com/privkey.pem nginx/ssl/key.pem

# Rebuild nginx
docker compose up -d --build nginx

# Set up auto-renewal
sudo certbot renew --dry-run
```

#### For Production with Commercial Certificate:

1. Obtain SSL certificate from your Certificate Authority
2. Replace `nginx/ssl/cert.pem` with your certificate
3. Replace `nginx/ssl/key.pem` with your private key
4. Rebuild Nginx: `docker-compose up -d --build nginx`

### 6. Backup Strategy

```bash
# Create backup script
cat > /opt/ipam/backup.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/opt/ipam/backups"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# Backup database
docker exec ipam_pg pg_dump -U ipam_user ipam > $BACKUP_DIR/ipam_db_$DATE.sql

# Backup configuration
cp .env $BACKUP_DIR/env_$DATE.bak

# Keep only last 7 backups
find $BACKUP_DIR -name "ipam_db_*.sql" -mtime +7 -delete
find $BACKUP_DIR -name "env_*.bak" -mtime +7 -delete

echo "Backup completed: $DATE"
EOF

chmod +x /opt/ipam/backup.sh

# Schedule daily backups (RHEL)
(crontab -l 2>/dev/null; echo "0 2 * * * /opt/ipam/backup.sh") | crontab -
```

**Windows Server Backup (PowerShell):**
```powershell
# Create backup script
$BackupScript = @"
`$BackupDir = "C:\ipam\backups"
`$Date = Get-Date -Format "yyyyMMdd_HHmmss"

New-Item -Path `$BackupDir -ItemType Directory -Force | Out-Null

# Backup database
docker exec ipam_pg pg_dump -U ipam_user ipam > "`$BackupDir\ipam_db_`$Date.sql"

# Backup configuration
Copy-Item .env "`$BackupDir\env_`$Date.bak"

# Keep only last 7 backups
Get-ChildItem "`$BackupDir\ipam_db_*.sql" | Where-Object {`$_.LastWriteTime -lt (Get-Date).AddDays(-7)} | Remove-Item
Get-ChildItem "`$BackupDir\env_*.bak" | Where-Object {`$_.LastWriteTime -lt (Get-Date).AddDays(-7)} | Remove-Item

Write-Host "Backup completed: `$Date"
"@

Set-Content -Path "C:\ipam\backup.ps1" -Value $BackupScript

# Schedule daily backups using Task Scheduler
$Action = New-ScheduledTaskAction -Execute "PowerShell.exe" -Argument "-File C:\ipam\backup.ps1"
$Trigger = New-ScheduledTaskTrigger -Daily -At 2:00AM
Register-ScheduledTask -TaskName "IPAM Backup" -Action $Action -Trigger $Trigger -User "SYSTEM"
```

### 7. Monitoring and Logs

```bash
# View real-time logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f app
docker-compose logs -f nginx
docker-compose logs -f db

# Check container resource usage
docker stats
```

---

## Troubleshooting

### Container Won't Start

```bash
# Check container status
docker-compose ps

# View detailed logs
docker-compose logs

# Restart specific service
docker-compose restart app

# Rebuild and restart
docker-compose up -d --build
```

### Database Connection Issues

```bash
# Check if PostgreSQL is healthy
docker exec ipam_pg pg_isready -U ipam_user -d ipam

# Check database logs
docker logs ipam_pg

# Verify environment variables
docker exec ipam_app env | grep DATABASE

# Restart database
docker-compose restart db
```

### Container Name Conflict
If you see an error like `The container name "/ipam_pg" is already in use`, but `docker ps` shows nothing:
1. Check stopped containers:
   ```bash
   docker ps -a
   ```
2. Remove the conflicting container:
   ```bash
   docker rm ipam_pg
   # Or remove all stopped containers
   docker container prune
   ```

### Port Conflicts (Windows)

```powershell
# Check what's using port 80
Get-NetTCPConnection -LocalPort 80

# Check what's using port 443
Get-NetTCPConnection -LocalPort 443

# Stop IIS if needed
Stop-Service W3SVC -Force
Set-Service W3SVC -StartupType Disabled
```

### Port Conflicts (RHEL)

```bash
# Check what's using port 80/443
sudo ss -tulpn | grep :80
sudo ss -tulpn | grep :443

# Stop conflicting service
sudo systemctl stop httpd
sudo systemctl disable httpd
```

### SSL Certificate Issues

```bash
# Regenerate self-signed certificate
cd nginx
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout ssl/key.pem \
  -out ssl/cert.pem

# Rebuild Nginx
cd ..
docker-compose up -d --build nginx
```

### Admin Login Not Working

```bash
# Reset admin password
docker exec ipam_app python -c "
from app.db import SessionLocal
from app.models import User
from sqlalchemy import select, delete

db = SessionLocal()
# Delete existing admin
db.execute(delete(User).where(User.username == 'admin'))
db.commit()
db.close()
"

# Restart app to recreate admin user
docker-compose restart app

# Verify admin user was created
docker logs ipam_app | grep -i "admin"
```

### Application Performance Issues

```bash
# Check resource usage
docker stats

# Increase container resources in docker-compose.yml
# Add under 'app' service:
#   deploy:
#     resources:
#       limits:
#         cpus: '2'
#         memory: 2G

# Restart services
docker-compose up -d
```

### Network Issues

```bash
# Recreate Docker network
docker-compose down
docker network rm ipam-network
docker network create ipam-network
docker-compose up -d
```

### Viewing Audit Logs

Navigate to **Settings → Audit Logs** (admin only) or access via API:
```bash
curl -k https://localhost/api/audit/logs?username=admin&password=admin123
```

### Common Error Messages

| Error | Solution |
|-------|----------|
| "Cannot connect to database" | Verify PostgreSQL is running: `docker-compose restart db` |
| "Port already in use" | Stop conflicting service or use different ports |
| "Container name already in use" | Remove stopped container: `docker rm <name>` |
| "no such image: ..." | Verify images loaded: `docker images` or run `docker load -i ipam_images.tar` |
| "Permission denied" | Check file permissions (`chmod -R +r .`) or disable SELinux (`sudo setenforce 0`) temporarily |
| "failed to solve: error from sender" | Use `docker compose up -d --no-build` or check file permissions |
| "SSL certificate error" | Regenerate certificates or accept self-signed cert in browser |
| "OIDC authentication failed" | Verify OIDC configuration and network connectivity |

---

## Maintenance

### Updating the Application

```bash
# Pull latest changes
cd /opt/ipam  # or C:\ipam on Windows
git pull

# Rebuild and restart
docker-compose down
docker-compose up -d --build

# Verify update
docker-compose ps
docker logs ipam_app
```

### Database Migrations

The application automatically applies database migrations on startup. If manual intervention is needed:

```bash
# Access database
docker exec -it ipam_pg psql -U ipam_user -d ipam

# Run SQL commands as needed
# \dt  -- List tables
# \q   -- Quit
```

### Scaling Considerations

For high-traffic environments:
1. Use a dedicated PostgreSQL server (not containerized)
2. Implement Redis for session storage
3. Use a load balancer for multiple app instances
4. Enable database connection pooling
5. Configure CDN for static assets

---

## Security Best Practices

1. **Change Default Credentials**: Always change the default admin password
2. **Use Strong Passwords**: Minimum 16 characters with complexity
3. **Enable HTTPS Only**: Set `https_only=True` in production
4. **Regular Updates**: Keep Docker images and system packages updated
5. **Firewall Configuration**: Only expose necessary ports
6. **Audit Logs**: Regularly review audit logs for suspicious activity
7. **Backup Encryption**: Encrypt backup files
8. **Network Segmentation**: Place IPAM in management VLAN
9. **Session Timeout**: Configure appropriate session timeout values
10. **SSL/TLS**: Use certificates from trusted CA in production

---

## Support and Resources

- **Documentation**: `/docs` endpoint for API documentation
- **Health Check**: `/health` endpoint for monitoring
- **Logs**: Access via `docker-compose logs`
- **Database**: PostgreSQL on port 5433 (external access)

---

## License

[Include your license information here]

## Version

Document Version: 1.0
Application Version: 1.0.0
Last Updated: 2026-01-04
