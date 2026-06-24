import argparse
import os
import re
import sys
import zipfile
import requests

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:140.0) Gecko/20100101 Firefox/140.0 CharaROMFDroidRepoTester/1.0"


def parse_masterlist(xml_path):
    """Deep-scans the XML layout, cleans individual items, and maps them into rigid 7-element dictionary blocks."""
    try:
        with open(xml_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        print(f"[-] Structural Error: Could not read manifest file: {e}", file=sys.stderr)
        sys.exit(1)

    # Strip out all XML comments cleanly first to prevent text segment cross-contamination
    clean_content = re.sub(r"", "", content, flags=re.DOTALL)

    # Extract all elements sequentially
    item_pattern = re.compile(r"<item>(.*?)</item>", re.DOTALL)
    items = [item.strip() for item in item_pattern.findall(clean_content)]

    if not items:
        print("[-] Alignment Error: No <item> tags found in target manifest asset.", file=sys.stderr)
        sys.exit(1)

    if len(items) % 7 != 0:
        print(
            f"[-] Alignment Error: Found {len(items)} fields. Total items must be an exact multiple of 7.",
            file=sys.stderr,
        )
        sys.exit(1)

    repositories = []
    for i in range(0, len(items), 7):
        repo_struct = {
            "name": items[i],
            "address": items[i + 1],
            "description": items[i + 2],
            "version": items[i + 3],
            "enabled": items[i + 4],
            "push": items[i + 5],
            "pubkey": items[i + 6],
        }
        repositories.append(repo_struct)

    return repositories


def emulate_client_sync_and_resolve(base_url):
    """Validates F-Droid repository access using localized, file-level redirect handling,

    strict content validation, and dual-variant trailing slash path attempts.
    """
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json,application/xml,application/java-archive,*/*",
        "Accept-Encoding": "gzip",
        "Connection": "keep-alive",
    }

    clean_base = base_url.rstrip("/")
    errors = []
    url_variants = [clean_base, clean_base + "/"]

    # --- METHOD A: TRY V2 INDEX PAYLOADS ---
    for variant in url_variants:
        try:
            res = requests.get(f"{variant}entry.json", headers=headers, allow_redirects=True, timeout=8)
            if res.status_code == 200 and "json" in res.headers.get("Content-Type", "").lower():
                try:
                    entry_data = res.json()
                    if "index" in entry_data and "numPackages" in entry_data["index"]:
                        resolved_base = res.url.split("/entry.json")[0].rstrip("/")
                        remote_name = entry_data.get("repo", {}).get("name")
                        return True, resolved_base, remote_name, f"V2 Sync OK ({entry_data['index']['numPackages']} apps)"
                except (ValueError, KeyError):
                    errors.append(f"entry.json parsing failed on variant path: {variant}")
            else:
                errors.append(f"entry.json HTTP {res.status_code} or type mismatch on variant: {variant}")
        except Exception as e:
            errors.append(f"entry.json network fault ({type(e).__name__}) on variant: {variant}")

    for variant in url_variants:
        try:
            res = requests.get(f"{variant}index-v2.json", headers=headers, allow_redirects=True, timeout=8)
            if res.status_code == 200 and "json" in res.headers.get("Content-Type", "").lower():
                try:
                    v2_data = res.json()
                    if "packages" in v2_data:
                        resolved_base = res.url.split("/index-v2.json")[0].rstrip("/")
                        remote_name = v2_data.get("repo", {}).get("name")
                        return True, resolved_base, remote_name, f"V2 Direct OK ({len(v2_data['packages'])} apps)"
                except (ValueError, KeyError):
                    errors.append(f"index-v2.json parsing failed on variant path: {variant}")
            else:
                errors.append(f"index-v2.json HTTP {res.status_code} or type mismatch on variant: {variant}")
        except Exception as e:
            errors.append(f"index-v2.json network fault ({type(e).__name__}) on variant: {variant}")

    # --- METHOD B: FALLBACK TO LEGACY V1 INDEX PROCESSING ---
    local_temp_jar = "sync_test_index.jar"
    for variant in url_variants:
        try:
            res = requests.get(f"{variant}index-v1.jar", headers=headers, allow_redirects=True, timeout=10)
            if res.status_code == 200 and "text/html" not in res.headers.get("Content-Type", "").lower():
                with open(local_temp_jar, "wb") as f:
                    f.write(res.content)

                is_valid_v1 = False
                package_count = 0
                remote_name = None

                with zipfile.ZipFile(local_temp_jar, "r") as archive:
                    if "index.xml" in archive.namelist():
                        xml_content = archive.read("index.xml").decode("utf-8")
                        package_count = len(re.findall(r"<package>", xml_content))
                        is_valid_v1 = True
                        
                        name_match = re.search(r'<repo\s+[^>]*name=["\']([^"\']+)["\']', xml_content)
                        if name_match:
                            remote_name = name_match.group(1)

                if os.path.exists(local_temp_jar):
                    os.remove(local_temp_jar)

                if is_valid_v1:
                    resolved_base = res.url.split("/index-v1.jar")[0].rstrip("/")
                    return True, resolved_base, remote_name, f"V1 Legacy Sync OK ({package_count} apps)"
            else:
                errors.append(f"index-v1.jar HTTP {res.status_code} or text/html loop caught on variant: {variant}")
        except Exception as e:
            errors.append(f"index-v1.jar decoding exception ({type(e).__name__}) on variant: {variant}")
            if os.path.exists(local_temp_jar):
                os.remove(local_temp_jar)

    unique_errors = list(dict.fromkeys(errors))
    verbose_diagnostic = " | Details: " + " -> ".join(unique_errors)
    return False, clean_base, None, verbose_diagnostic


def run_pipeline(input_path, output_path):
    # Parse the incoming structure cleanly right out of the gate
    repositories = parse_masterlist(input_path)
    print(f"[*] Initializing Context-Aware Architecture Audit across {len(repositories)} paths...\n")

    verified_queue = []
    disabled_count = 0
    updated_url_count = 0
    updated_name_count = 0

    for idx, repo in enumerate(repositories, start=1):
        print(f"[{idx}/{len(repositories)}] Auditing: '{repo['name']}'")
        print(f"    ↳ Target: {repo['address']}")

        sync_success, resolved_address, remote_name, status_message = emulate_client_sync_and_resolve(repo["address"])

        if repo["address"].rstrip("/") != resolved_address.rstrip("/"):
            if repo["address"].startswith("https://") and resolved_address.startswith("http://"):
                print("    [!] WARNING: Aborting insecure downgrade redirection patch to maintain manifest security.")
            else:
                print(f"    [+] REDIRECTED: {repo['address']} -> {resolved_address}")
                repo["address"] = resolved_address
                updated_url_count += 1

        if sync_success and remote_name and remote_name.strip() != repo["name"]:
            clean_name = remote_name.strip()
            if clean_name:
                print(f"    [+] NAME MUTATED: '{repo['name']}' -> '{clean_name}'")
                repo["name"] = clean_name
                updated_name_count += 1

        if sync_success:
            print(f"    [✓] SUCCESS: {status_message}\n")
            verified_queue.append(repo)
        else:
            print(f"    [✗] FAILED: {status_message}")
            print("    [!] Flagging entry inside deployment array wrapper as disabled.\n")
            repo["enabled"] = "0"
            disabled_count += 1
            verified_queue.append(repo)

    # Reassemble XML layout forcing exact structured comments on every single iterated block
    lines = [
        '<?xml version="1.0" encoding="utf-8"?>',
        "<resources>",
        '    <string-array name="user_repositories">',
    ]

    for r in verified_queue:
        lines.append("        ")
        lines.append(f"        <item>{r['name']}</item>")
        lines.append("        ")
        lines.append(f"        <item>{r['address']}</item>")
        lines.append("        ")
        lines.append(f"        <item>{r['description']}</item>")
        lines.append("        ")
        lines.append(f"        <item>{r['version']}</item>")
        lines.append("        ")
        lines.append(f"        <item>{r['enabled']}</item>")
        lines.append("        ")
        lines.append(f"        <item>{r['push']}</item>")
        lines.append("        ")
        lines.append(f"        <item>{r['pubkey']}</item>")

    lines.append("    </string-array>")
    lines.append("</resources>\n")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"{'='*60}")
    print(f"[+] Pipeline Execution Context Finalized.")
    print(f"    - Total Processed Entries: {len(repositories)}")
    print(f"    - Target Names Dynamically Updated: {updated_name_count}")
    print(f"    - Target Routes Patched via Redirect: {updated_url_count}")
    print(f"    - Inactive Repositories Flagged/Disabled: {disabled_count}")
    print(f"    - Output Saved with uniform structural comments: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Context-aware F-Droid repository synchronization checker and list optimization tool."
    )
    parser.add_argument("input_xml", help="Path to your masterlist XML configuration asset")
    parser.add_argument("-o", "--output", help="Path for output verified XML (Default: Overwrites source file)")

    args = parser.parse_args()
    output_destination = args.output if args.output else args.input_xml

    if not os.path.isfile(args.input_xml):
        print(f"[-] Execution Failure: Target path '{args.input_xml}' not found.", file=sys.stderr)
        sys.exit(1)

    run_pipeline(args.input_xml, output_destination)


if __name__ == "__main__":
    main()