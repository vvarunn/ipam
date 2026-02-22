# IPAM Airgap Packaging Script (Windows)
$ErrorActionPreference = "Stop"

Write-Host "Starting IPAM Airgap Packaging..." -ForegroundColor Cyan

# 1. Build and Pull Images
Write-Host "Building Docker Images..."
docker compose build
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to build images. Check Docker output above."
}

Write-Host "Pulling External Images..."
docker compose pull db
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to pull external images (db). Check internet connection/proxy."
}

# 2. Define Images to Save
# Must match docker-compose.yml tags
$Images = @(
    "ipam-app:latest",
    "ipam-nginx:latest",
    "postgres:16"
)

# 3. Save Images
$TarFile = "ipam_images.tar"
Write-Host "Saving images to $TarFile..."
docker save -o $TarFile $Images
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to save docker images."
}

# 4. Create Package Zip
$ZipFile = "D:\projects\ipam_airgap_package.zip"
# Ensure we exclude the temp dir itself and large build artifacts
$Excludes = @(".git", ".venv", "__pycache__", ".idea", ".vscode", "node_modules", "*.zip", "*.tar", "ipam_pkg_temp")

Write-Host "Creating deployment package: $ZipFile..."

# Create a temporary directory for packaging
$TempDir = "ipam_pkg_temp"
if (Test-Path $TempDir) { Remove-Item -Recurse -Force $TempDir }
New-Item -ItemType Directory -Force -Path $TempDir | Out-Null

# Copy project files
# Note: Get-ChildItem -Exclude applies to the Name property.
Get-ChildItem -Path . -Exclude $Excludes | Copy-Item -Destination $TempDir -Recurse -Force

# Move the tarball into temp dir
Move-Item $TarFile "$TempDir\$TarFile" -Force

# Zip the directory
Compress-Archive -Path "$TempDir\*" -DestinationPath $ZipFile -Force

# Cleanup
Remove-Item -Recurse -Force $TempDir

Write-Host "Packaging Complete!" -ForegroundColor Green
Write-Host "Artifact: $ZipFile"
