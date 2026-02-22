from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, File, UploadFile, Form
from sqlalchemy.orm import Session
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
import json
import subprocess
import os
import zipfile
import shutil

from app.db import get_session
from app.models import Settings
from app.deps import require_admin
from app.crud import audit

router = APIRouter(prefix='/api/settings', tags=['settings'])

class SSOSettings(BaseModel):
    sso_type: str = 'none'  # 'none', 'oidc', 'saml'
    
    # OIDC Fields
    discovery_url: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    redirect_uri: Optional[str] = None
    scopes: str = 'openid profile email'
    
    # SAML Fields
    saml_idp_entity_id: Optional[str] = None
    saml_idp_sso_url: Optional[str] = None
    saml_idp_x509_cert: Optional[str] = None

class AppSettings(BaseModel):
    app_url: Optional[str] = None

def get_setting(db: Session, key: str) -> Optional[str]:
    """Get a setting value from database"""
    setting = db.scalar(select(Settings).where(Settings.key == key))
    return setting.value if setting else None

def set_setting(db: Session, key: str, value: str, encrypted: bool = False, actor: str = 'admin'):
    """Set a setting value in database"""
    setting = db.scalar(select(Settings).where(Settings.key == key))
    old_value = setting.value if setting else None
    
    if setting:
        setting.value = value
        setting.encrypted = encrypted
        setting.updated_by = actor
    else:
        setting = Settings(key=key, value=value, encrypted=encrypted, updated_by=actor)
        db.add(setting)
    
    audit(db, actor, 'UPDATE_SETTING', 'settings', None, {'key': key, 'value': old_value}, {'key': key})
    return setting

@router.get('/sso', response_model=SSOSettings)
def get_sso_settings(
    db: Session = Depends(get_session),
    admin: dict = Depends(require_admin)
):
    """Get SSO configuration (admin only)"""
    # Fallback to older oidc_config key if sso_config doesn't exist yet
    settings_json = get_setting(db, 'sso_config')
    if not settings_json:
        old_oidc = get_setting(db, 'oidc_config')
        if old_oidc:
            try:
                old_data = json.loads(old_oidc)
                # Migrate active OIDC
                if old_data.get('enabled'):
                    old_data['sso_type'] = 'oidc'
                return SSOSettings(**old_data)
            except:
                pass
                
    if settings_json:
        try:
            return SSOSettings(**json.loads(settings_json))
        except:
            pass
    
    return SSOSettings()

@router.put('/sso')
def update_sso_settings(
    settings: SSOSettings,
    db: Session = Depends(get_session),
    admin: dict = Depends(require_admin)
):
    """Update SSO configuration (admin only)"""
    settings_dict = settings.model_dump()
    settings_json = json.dumps(settings_dict)
    
    set_setting(db, 'sso_config', settings_json, encrypted=False, actor=admin.get('username', 'admin'))
    db.commit()
    
    return {'ok': True, 'message': 'SSO settings updated successfully'}

@router.get('/application', response_model=AppSettings)
def get_app_settings(
    db: Session = Depends(get_session),
    admin: dict = Depends(require_admin)
):
    """Get Application Configuration (admin only)"""
    settings_json = get_setting(db, 'app_config')
    
    if settings_json:
        try:
            return AppSettings(**json.loads(settings_json))
        except:
            pass
    
    return AppSettings()

@router.put('/application')
def update_app_settings(
    app_url: Optional[str] = Form(None),
    cert_file: Optional[UploadFile] = File(None),
    key_file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_session),
    admin: dict = Depends(require_admin)
):
    """Update Application Configuration (admin only)"""
    settings_dict = {'app_url': app_url}
    settings_json = json.dumps(settings_dict)
    
    set_setting(db, 'app_config', settings_json, encrypted=False, actor=admin.get('username', 'admin'))
    db.commit()
    
    ssl_dir = '/host_src/nginx/ssl' if os.path.exists('/host_src') else 'nginx/ssl'
    os.makedirs(ssl_dir, exist_ok=True)
    
    files_updated = False
    
    if cert_file and cert_file.filename:
        cert_path = os.path.join(ssl_dir, 'cert.pem')
        with open(cert_path, 'wb') as f:
            f.write(cert_file.file.read())
        files_updated = True
            
    if key_file and key_file.filename:
        key_path = os.path.join(ssl_dir, 'key.pem')
        with open(key_path, 'wb') as f:
            f.write(key_file.file.read())
        files_updated = True

    msg = 'Application settings updated successfully.'
    if files_updated:
        try:
            subprocess.run(['docker', 'restart', 'ipam_nginx'], check=False)
            msg += ' Rescheduled nginx to apply new certificates.'
        except Exception as e:
            print(f"Failed to restart nginx: {e}")
            msg += ' However, failed to restart nginx.'
    
    return {'ok': True, 'message': msg}

@router.get('/siem')
def get_siem_settings(
    db: Session = Depends(get_session),
    admin: dict = Depends(require_admin)
):
    """Get SIEM export settings (admin only)"""
    settings_json = get_setting(db, 'siem_config')
    
    if settings_json:
        try:
            return json.loads(settings_json)
        except:
            pass
    
    return {
        'enabled': False,
        'endpoint': '',
        'format': 'json'
    }

@router.put('/siem')
def update_siem_settings(
    settings: dict,
    db: Session = Depends(get_session),
    admin: dict = Depends(require_admin)
):
    """Update SIEM export settings (admin only)"""
    settings_json = json.dumps(settings)
    
    set_setting(db, 'siem_config', settings_json, encrypted=False, actor=admin.get('username', 'admin'))
    db.commit()
    
    return {'ok': True, 'message': 'SIEM settings updated successfully'}

def run_update_script():
    """Background task to run git pull and rebuild containers"""
    
    # Use /host_src if it exists, otherwise fallback to the current directory (for bare-metal/local deployments)
    http_proxy = os.getenv('HTTP_PROXY', os.getenv('http_proxy', ''))
    https_proxy = os.getenv('HTTPS_PROXY', os.getenv('https_proxy', ''))
    no_proxy = os.getenv('NO_PROXY', os.getenv('no_proxy', ''))
    
    script = f"""
    HOST_DIR="/host_src"
    if [ ! -d "$HOST_DIR" ]; then
        HOST_DIR="."
    fi
    
    cd $HOST_DIR
    echo "Starting update process at $(date)..." > update_status.txt
    echo "Working directory: $(pwd)" >> update_status.txt
    
    # Export proxy settings
    if [ -n "{http_proxy}" ]; then export HTTP_PROXY="{http_proxy}"; export http_proxy="{http_proxy}"; fi
    if [ -n "{https_proxy}" ]; then export HTTPS_PROXY="{https_proxy}"; export https_proxy="{https_proxy}"; fi
    if [ -n "{no_proxy}" ]; then export NO_PROXY="{no_proxy}"; export no_proxy="{no_proxy}"; fi
    
    # Configure git safe directory for the host mount
    git config --global --add safe.directory $HOST_DIR
    
    echo -e "\\n> Pulling latest changes from GitHub..." >> update_status.txt
    git pull origin main >> update_status.txt 2>&1
    
    echo -e "\\n> Rebuilding containers..." >> update_status.txt
    # Fallback to docker-compose if docker compose is missing
    if docker compose version > /dev/null 2>&1; then
        docker compose up --build -d >> update_status.txt 2>&1
    else
        docker-compose up --build -d >> update_status.txt 2>&1
    fi
    
    echo -e "\\nUpdate process initiated. Containers will restart shortly." >> update_status.txt
    """
    try:
        # Run in bash to execute the compound commands
        subprocess.Popen(['bash', '-c', script], start_new_session=True)
    except Exception as e:
        print(f"Error starting update script: {e}")
        try:
            with open('update_status.txt', 'a') as f:
                f.write(f"\\nError starting update script: {e}\\n")
        except:
            pass

@router.post('/update_app')
def trigger_app_update(
    background_tasks: BackgroundTasks,
    admin: dict = Depends(require_admin)
):
    """Trigger application update from GitHub (admin only)"""
    # Create or clear the status file before starting
    try:
        with open('update_status.txt', 'w') as f:
            f.write("Initializing update sequence...\\n")
    except Exception:
        pass
        
    background_tasks.add_task(run_update_script)
    return {'ok': True, 'message': 'Update sequence initiated. The application will restart shortly.'}

@router.get('/update_status')
def get_update_status(
    admin: dict = Depends(require_admin)
):
    """Get the current output of the application update script (admin only)"""
    try:
        if os.path.exists('update_status.txt'):
            with open('update_status.txt', 'r') as f:
                content = f.read()
            return {'ok': True, 'status': content}
        else:
            return {'ok': True, 'status': 'Update status log not found. Update may not have started yet or has finished.'}
    except Exception as e:
        return {'ok': False, 'status': f"Error reading status: {str(e)}"}

def run_zip_update_script(zip_path: str):
    """Background task to extract zip, load images, and rebuild containers"""
    host_dir = '/host_src'
    if not os.path.exists(host_dir):
        host_dir = '.'
        
    def log_status(msg):
        try:
            with open('update_status.txt', 'a') as f:
                f.write(f"{msg}\\n")
        except:
            pass

    try:
        log_status(f"Starting zip update process at $(date)...")
        log_status(f"Working directory: {host_dir}")
        log_status(f"\\n> Extracting uploaded package...")
        
        # Extract the zip file, overwriting existing files
        print(f"Extracting {zip_path} to {host_dir}...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(host_dir)
            
        print("Zip extraction completed.")
        log_status(f"> Package extracted successfully.")
        
        # Load docker images and restart containers
        script = f"""
        cd {host_dir}
        if [ -f "ipam_images.tar" ]; then
            echo "\\n> Loading docker images from tar archive (this may take a few minutes)..." >> update_status.txt
            docker load -i ipam_images.tar >> update_status.txt 2>&1
            echo "> Images loaded." >> update_status.txt
        fi
        
        echo -e "\\n> Restarting application stack..." >> update_status.txt
        docker compose up -d --no-build >> update_status.txt 2>&1
        echo -e "\\nUpdate process initiated. Containers will restart shortly." >> update_status.txt
        """
        
        # Run in bash to execute the compound commands
        subprocess.Popen(['bash', '-c', script], start_new_session=True)
    except Exception as e:
        print(f"Error during zip update sequence: {e}")
        log_status(f"\\nError during zip update sequence: {e}")
    finally:
        # Clean up the uploaded zip file if it still exists
        try:
            if os.path.exists(zip_path):
                os.remove(zip_path)
        except Exception:
            pass

@router.post('/update_app_zip')
def trigger_zip_app_update(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    admin: dict = Depends(require_admin)
):
    """Trigger application update via uploaded zip file (admin only)"""
    if not file.filename.endswith('.zip'):
        raise HTTPException(status_code=400, detail="Only .zip files are allowed for updates")
        
    host_dir = '/host_src'
    if not os.path.exists(host_dir):
        # Fallback for dev environment without volume mounts
        host_dir = '.'
        
    # Create or clear the status file before starting
    try:
        with open('update_status.txt', 'w') as f:
            f.write("Initializing update sequence via Zip upload...\\n")
    except Exception:
        pass
        
    temp_zip_path = os.path.join(host_dir, 'update_temp.zip')
    
    try:
        # Save uploaded file
        with open(temp_zip_path, 'wb') as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # Schedule the background worker
        background_tasks.add_task(run_zip_update_script, temp_zip_path)
        
        return {
            'ok': True, 
            'message': 'Update package uploaded successfully. The application is extracting the files and will restart shortly.'
        }
    except Exception as e:
        if os.path.exists(temp_zip_path):
            os.remove(temp_zip_path)
        raise HTTPException(status_code=500, detail=f"Failed to process update package: {str(e)}")
