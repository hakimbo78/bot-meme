import zipfile
import os
import sys

def create_zip():
    print("Creating deploy_v6.zip...")
    try:
        with zipfile.ZipFile('deploy_v6.zip', 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk('.'):
                # Exclude dirs
                dirs[:] = [d for d in dirs if d not in ['.venv', '__pycache__', '.git', 'logs', 'artifacts']]
                for file in files:
                    if file.endswith('.zip') or file.endswith('.tar.gz') or 'deploy' in file: continue
                    
                    file_path = os.path.join(root, file)
                    # Normalize arcname to use forward slashes
                    arcname = os.path.relpath(file_path, '.').replace(os.path.sep, '/')
                    zipf.write(file_path, arcname)
        print("Zip created successfully.")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    create_zip()
