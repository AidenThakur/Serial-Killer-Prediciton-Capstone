"""
Aiden Thakur
The purpose of this python file is to download homicide data from the Crime Open Database (CODE) via OSF.
All 21 cities, all available years, filtered to homicide offenses only.(Looking at cities nears major traffic networks)
Outputs: homicide_data.csv
 
Source: Crime Open Database — https://osf.io/zyaqn/ (<- the website)
"""
 
import io
import re
import tempfile
from pathlib import Path
 
import pandas as pd
import requests
import pyreadr
 
 
# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
OSF_NODE = "zyaqn"
OSF_API = "https://api.osf.io/v2"
OUTPUT_FILE = "homicide_data.csv"
 
 
def fetch_rds_files(folder_name: str = "Data for R package") -> list[dict]:
    """Walk the OSF storage and return download info for all core .Rds files."""
 
    # Find the data folder
    url = f"{OSF_API}/nodes/{OSF_NODE}/files/osfstorage/"
    folder_url = None
 
    while url:
        resp = requests.get(url, params={"page[size]": 100})
        resp.raise_for_status()
        data = resp.json()
        for item in data.get("data", []):
            attrs = item.get("attributes", {})
            if attrs.get("kind") == "folder" and attrs.get("name") == folder_name:
                folder_url = item["relationships"]["files"]["links"]["related"]["href"]
                break
        if folder_url:
            break
        url = data.get("links", {}).get("next")
 
    if not folder_url:
        raise RuntimeError(f"Could not find '{folder_name}' folder on OSF.")
 
    # Paginate through folder contents, grab only core files
    pattern = re.compile(
        r"^crime_open_database_core_(.+?)_(\d{4})\.Rds$", re.IGNORECASE
    )
    files = []
    page = folder_url
 
    while page:
        resp = requests.get(page, params={"page[size]": 100})
        resp.raise_for_status()
        data = resp.json()
        for item in data.get("data", []):
            name = item.get("attributes", {}).get("name", "")
            m = pattern.match(name)
            if m:
                city = m.group(1).replace("_", " ").title()
                if city == "All":
                    continue  # skips aggregate files, download per-city
                files.append({
                    "name": name,
                    "city": city,
                    "year": int(m.group(2)),
                    "download_url": item["links"]["download"],
                })
        page = data.get("links", {}).get("next")
 
    return files
 
 
def download_rds_to_df(url: str) -> pd.DataFrame:
    """Download an .Rds file and return it as a pandas DataFrame."""
    resp = requests.get(url)
    resp.raise_for_status()
 
    with tempfile.NamedTemporaryFile(suffix=".Rds", delete=False) as tmp:
        tmp.write(resp.content)
        tmp_path = tmp.name
 
    try:
        result = pyreadr.read_r(tmp_path)
        return list(result.values())[0]
    finally:
        Path(tmp_path).unlink(missing_ok=True)
 
 
def main():
    print("=" * 60)
    print("Crime Open Database — Homicide Data Download")
    print("=" * 60)
 
    # Step 1: Get file listing
    print("\nFetching file listing from OSF...")
    files = fetch_rds_files()
    cities = sorted(set(f["city"] for f in files))
    years = sorted(set(f["year"] for f in files))
    print(f"Found {len(files)} core files across {len(cities)} cities")
    print(f"Year range: {min(years)}-{max(years)}")
    print(f"Cities: {', '.join(cities)}")
 
    # Step 2: Download each file and filter to homicides
    print(f"\nDownloading and filtering to homicide offenses...")
    all_homicides = []
    total_files = len(files)
 
    for i, f in enumerate(files, 1):
        print(f"  [{i}/{total_files}] {f['city']} {f['year']}...", end=" ", flush=True)
        try:
            df = download_rds_to_df(f["download_url"])
            homicides = df[df["offense_group"] == "homicide offenses"]
            print(f"{len(homicides):,} homicides")
            if len(homicides) > 0:
                all_homicides.append(homicides)
        except Exception as e:
            print(f"ERROR: {e}")
 
    # Step 3: Combine and save
    if not all_homicides:
        print("\nNo homicide records found!")
        return
 
    combined = pd.concat(all_homicides, ignore_index=True)
    combined.to_csv(OUTPUT_FILE, index=False)
 
    print("\n" + "=" * 60)
    print(f"Done! Saved {len(combined):,} homicide records to {OUTPUT_FILE}")
    print(f"Cities: {combined['city_name'].nunique()}")
    print(f"Year range: {combined['date_single'].str[:4].min()}-{combined['date_single'].str[:4].max()}")
    print(f"File size: {Path(OUTPUT_FILE).stat().st_size / 1024 / 1024:.1f} MB")
    print("=" * 60)
 
 
if __name__ == "__main__":
    main()