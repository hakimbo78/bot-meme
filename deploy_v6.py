import zipfile
import sys
import os

try:
    print("Extracting deploy_v6.zip...")
    with zipfile.ZipFile('deploy_v6.zip', 'r') as z:
        z.extractall('.')
    print("Clean extraction successful.")
except Exception as e:
    print(f"Extraction failed: {e}")
    sys.exit(1)
