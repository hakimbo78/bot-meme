import zipfile
try:
    print("Extracting deploy_clean.zip...")
    with zipfile.ZipFile('deploy_clean.zip', 'r') as z:
        z.extractall('.')
    print("Clean extraction successful.")
except Exception as e:
    print(f"Extraction failed: {e}")
