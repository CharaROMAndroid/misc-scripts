import argparse
import os
import re
import sys
import json
import zipfile
import requests

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:140.0) Gecko/20100101 Firefox/140.0 CharaROMFDroidRepoTester/1.0"

def locate_axpos_repositories(xml_path):
    """Scans the masterlist XML for repository addresses explicitly matching AXP.OS."""
    try:
        with open(xml_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        print(f"Error: Could not read file '{xml_path}': {e}", file=sys.stderr)
        sys.exit(1)

    pattern = re.compile(r"(|<item>(.*?)</item>)", re.DOTALL)
    tokens = pattern.findall(content)

    axp_repos = []
    current_block = []

    for token in tokens:
        full_match, item_text = token
        if full_match.startswith("<item>"):
            current_block.append(item_text.strip())

        if len(current_block) == 7:
            name = current_block[0]
            address = current_block[1]

            if "axp.os" in name.lower() or "axp.os" in address.lower():
                axp_repos.append({"name": name, "address": address.rstrip("/")})
            current_block = []

    return axp_repos

def extract_apk_filenames(repo_url):
    """Attempts to read modern index-v2.json, falling back to legacy index-v1.jar if necessary."""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json,text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Connection": "keep-alive"
    }
    
    # --- METHOD A: TRY MODERN V2 JSON INDEX ---
    v2_url = f"{repo_url}/index-v2.json"
    print(f"    [*] Attempting Modern V2 Index: {v2_url}")
    try:
        response = requests.get(v2_url, headers=headers, timeout=15)
        if response.status_code == 200:
            data = response.json()
            apk_files = []
            
            # F-Droid index-v2 structures store packages inside a primary dictionary map
            packages = data.get("packages", {})
            for pkg_id, pkg_meta in packages.items():
                versions = pkg_meta.get("versions", {})
                for ver_id, ver_meta in versions.items():
                    manifest = ver_meta.get("manifest", {})
                    # Look for the filename inside the file/name block structure
                    file_info = ver_meta.get("file", {})
                    name_attr = file_info.get("name") or manifest.get("apkName")
                    if name_attr:
                        # Strip subdirectories like "/repo/" if included in name string
                        clean_name = name_attr.split("/")[-1]
                        apk_files.append(clean_name)
            
            if apk_files:
                print("    [+] Successfully parsed index-v2 structure!")
                return sorted(list(set(apk_files)))
    except Exception as e:
        print(f"    [-] V2 parse bypass or error: {e}")

    # --- METHOD B: FALLBACK TO LEGACY JAR STRUCT ---
    jar_url = f"{repo_url}/index-v1.jar"
    local_jar = "temp_index.jar"
    print(f"    [*] Falling back to Legacy V1 Index: {jar_url}")
    try:
        response = requests.get(jar_url, headers=headers, timeout=15)
        if response.status_code == 200:
            with open(local_jar, "wb") as f:
                f.write(response.content)

            apk_files = []
            with zipfile.ZipFile(local_jar, "r") as z:
                if "index.xml" in z.namelist():
                    xml_data = z.read("index.xml").decode("utf-8")
                    apk_files = re.findall(r"<apkname>(.*?)</apkname>", xml_data)

            if os.path.exists(local_jar):
                os.remove(local_jar)

            if apk_files:
                print("    [+] Successfully parsed index-v1 structure!")
                return sorted(list(set(apk_files)))
        else:
            print(f"    [!] Server responded with status code: {response.status_code}")
    except Exception as e:
        print(f"    [!] V1 Fallback Error: {e}")
        if os.path.exists(local_jar):
            os.remove(local_jar)
            
    return []

def download_apk_files(repo_url, apk_list, output_directory):
    """Downloads each discovered binary sequentially into the target archive path."""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "*/*",
        "Connection": "keep-alive"
    }
    os.makedirs(output_directory, exist_ok=True)

    for idx, apk_name in enumerate(apk_list, start=1):
        target_download_url = f"{repo_url}/{apk_name}"
        destination_path = os.path.join(output_directory, apk_name)

        if os.path.exists(destination_path):
            print(f"    [{idx}/{len(apk_list)}] Already mirrored: {apk_name}")
            continue

        print(f"    [{idx}/{len(apk_list)}] Archiving: {apk_name}...", end="", flush=True)
        try:
            res = requests.get(target_download_url, headers=headers, timeout=30, stream=True)
            if res.status_code == 200:
                with open(destination_path, "wb") as f:
                    for chunk in res.iter_content(chunk_size=8192):
                        f.write(chunk)
                print(" DONE")
            else:
                print(f" FAILED (Status Code: {res.status_code})")
        except requests.RequestException as e:
            print(f" ERROR: {e}")

def main():
    parser = argparse.ArgumentParser(
        description="Extract and safely mirror all application packages from steadfasterX's active AXP.OS servers."
    )
    parser.add_argument("input_xml", help="Path to your checked, validated masterlist XML file")
    parser.add_argument("-d", "--dir", default="axpos_mirror", help="Base directory folder to save downloaded assets")

    args = parser.parse_args()

    if not os.path.isfile(args.input_xml):
        print(f"Error: Master list '{args.input_xml}' not found.")
        sys.exit(1)

    print("[*] Searching manifest entries for AXP.OS configuration targets...")
    targets = locate_axpos_repositories(args.input_xml)

    if not targets:
        print("[-] No AXP.OS repository lines found matching target criteria.")
        sys.exit(0)

    print(f"[+] Found {len(targets)} active AXP.OS repository endpoints.")

    for target in targets:
        print(f"\n::: Processing: {target['name']} :::")
        print(f"    Base URL: {target['address']}")

        apks = extract_apk_filenames(target["address"])

        if not apks:
            print("    [!] No target package names found or index unreachable.")
            continue

        print(f"    [+] Located {len(apks)} deployment packages on server.")

        safe_folder_name = re.sub(r"[^\w\-_]", "_", target["name"])
        repo_output_dir = os.path.join(args.dir, safe_folder_name)

        download_apk_files(target["address"], apks, repo_output_dir)

    print(f"\n[+] Mirror operations finished. All assets saved inside: {args.dir}")

if __name__ == "__main__":
    main()