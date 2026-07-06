"""
Quick diagnostic: tests service account auth + Drive folder access.
Run with:  python test_connection.py
"""

ROOT_FOLDER_ID = "0B5x6_lwAEhFZdkJnY3c1X1NxTVE"

print("=" * 55)
print("  SHPE Analytics — Service Account Diagnostic")
print("=" * 55)

# 1. Check credentials file
import os
cred_path = os.path.join(os.path.dirname(__file__), "service_account.json")
if not os.path.exists(cred_path):
    print(f"\n[FAIL] service_account.json not found at:\n       {cred_path}")
    exit(1)
print(f"\n[OK]  service_account.json found")

# 2. Parse the JSON to show which account is being used
import json
with open(cred_path) as f:
    cred_data = json.load(f)
print(f"[OK]  Service account email: {cred_data.get('client_email', '(not found)')}")
print(f"      Project ID:            {cred_data.get('project_id', '(not found)')}")

# 3. Build the Drive + Sheets services
print("\n[..] Building Google API services...")
try:
    from backend import get_services
    drive, sheets = get_services()
    print("[OK]  google-auth + Drive/Sheets clients built successfully")
except Exception as e:
    print(f"[FAIL] Could not build services: {e}")
    exit(1)

# 4. Try listing the root folder
print(f"\n[..] Listing root folder ({ROOT_FOLDER_ID})...")
try:
    resp = drive.files().list(
        q=f"'{ROOT_FOLDER_ID}' in parents and trashed=false",
        fields="files(id, name, mimeType)",
        pageSize=50,
    ).execute()
    items = resp.get("files", [])
    if not items:
        print("[WARN] Root folder is accessible but contains no items.")
        print("       Check that the service account has been shared on this folder.")
    else:
        folders = [i for i in items if "folder" in i["mimeType"]]
        sheets_  = [i for i in items if "spreadsheet" in i["mimeType"]]
        other    = [i for i in items if i not in folders and i not in sheets_]
        print(f"[OK]  Root folder accessible — {len(items)} item(s) found:")
        print(f"        Folders:      {len(folders)}")
        print(f"        Spreadsheets: {len(sheets_)}")
        print(f"        Other:        {len(other)}")
        print()
        print("  Year folders detected:")
        for f in sorted(folders, key=lambda x: x["name"]):
            print(f"    • {f['name']}  (id: {f['id']})")
except Exception as e:
    print(f"[FAIL] Could not list root folder: {e}")
    print()
    print("  Possible causes:")
    print("  1. The service account has NOT been shared on the Drive folder.")
    print("     → Open the folder in Drive → Share → paste the service account email.")
    print("  2. The Drive API is not enabled for this project.")
    print("     → console.cloud.google.com → APIs & Services → Enable 'Google Drive API'")
    print("  3. The ROOT_FOLDER_ID in server.py / test_connection.py is wrong.")
    print(f"     → Current value: {ROOT_FOLDER_ID}")
    exit(1)

print("\n" + "=" * 55)
print("  All checks passed — service account is working.")
print("=" * 55)
