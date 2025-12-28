import zipfile
import sys
import os

try:
    print("Extracting deploy.zip...")
    with zipfile.ZipFile('deploy.zip', 'r') as z:
        z.extractall('.')
    print("Extraction successful.")
except Exception as e:
    print(f"Extraction failed: {e}")
    sys.exit(1)
