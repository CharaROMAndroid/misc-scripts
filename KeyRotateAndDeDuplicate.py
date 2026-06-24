import argparse
import os
import re
import sys
import xml.etree.ElementTree as ET
import requests
from xml.dom import minidom

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:140.0) Gecko/20100101 Firefox/140.0 CharaROMFDroidRepoTester/1.0"


def canonicalize_url(url_string):
    """Normalizes a URL string to prevent layout duplication caused by minor variations."""
    if not url_string:
        return ""
    # Strip whitespace, drop trailing slashes, and cast to lowercase
    return url_string.strip().rstrip("/").lower()


def parse_and_deduplicate(xml_path):
    """Parses structural item blocks and filters duplicates strictly by canonical URL destinations."""
    try:
        with open(xml_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        print(f"Error: Unable to process file maps: {e}", file=sys.stderr)
        sys.exit(1)

    pattern = re.compile(r"(|<item>(.*?)</item>)", re.DOTALL)
    tokens = pattern.findall(content)

    unique_repos = []
    seen_urls = set()
    duplicate_count = 0
    current_block = []

    for token in tokens:
        full_match, item_text = token
        if full_match.startswith("<item>"):
            current_block.append(item_text.strip())

        if len(current_block) == 7:
            repo_struct = {
                "name": current_block[0],
                "address": current_block[1],
                "description": current_block[2],
                "version": current_block[3],
                "enabled": current_block[4],
                "push": current_block[5],
                "pubkey": current_block[6],
            }

            canonical_address = canonicalize_url(repo_struct["address"])

            if canonical_address in seen_urls:
                duplicate_count += 1
            else:
                seen_urls.add(canonical_address)
                unique_repos.append(repo_struct)

            current_block = []

    if duplicate_count > 0:
        print(
            f"[*] Verification Phase: Found and intercepted {duplicate_count} layout duplicate(s)."
        )
    return unique_repos


def query_signing_fingerprint(url):
    """Pings verification paths to test stability and capture modern rotated signing tokens."""
    base_url = url.rstrip("/")
    headers = {"User-Agent": USER_AGENT, "Connection": "keep-alive"}

    # Attempt lookup via modern v2 endpoint mappings
    try:
        response = requests.get(
            f"{base_url}/index-v2.json", headers=headers, timeout=8
        )
        if response.status_code == 200:
            # Query standard deployment fingerprint headers returned by the server
            live_key = response.headers.get("X-Repo-Signing-Fingerprint", None)
            return True, live_key
    except requests.RequestException:
        pass

    # Fallback status confirmation check if v2 structures do not pass custom headers
    try:
        fallback_res = requests.head(
            f"{base_url}/index.xml", headers=headers, timeout=5
        )
        if fallback_res.status_code == 200:
            return True, None
    except requests.RequestException:
        pass

    return False, None


def compile_optimized_xml(repos):
    """Generates standard, structured XML layouts directly from data maps."""
    lines = []
    lines.append('<?xml version="1.0" encoding="utf-8"?>')
    lines.append("<resources>")
    lines.append('    <string-array name="user_repositories">')

    for repo in repos:
        lines.append("        ")
        lines.append(f"        <item>{repo['name']}</item>")
        lines.append("        ")
        lines.append(f"        <item>{repo['address']}</item>")
        lines.append("        ")
        lines.append(f"        <item>{repo['description']}</item>")
        lines.append("        ")
        lines.append(f"        <item>{repo['version']}</item>")
        lines.append("        ")
        lines.append(f"        <item>{repo['enabled']}</item>")
        lines.append("        ")
        lines.append(f"        <item>{repo['push']}</item>")
        lines.append("        ")
        lines.append(f"        <item>{repo['pubkey']}</item>")

    lines.append("    </string-array>")
    lines.append("</resources>")
    return "\n".join(lines)


def run_maintenance_pipeline(input_path, output_path):
    """Processes deduplication and performs automatic key rotation updates."""
    print(f"[*] Processing file target: {input_path}")
    deduplicated_repos = parse_and_deduplicate(input_path)

    print(
        f"[+] Deduplication complete. Evaluated {len(deduplicated_repos)} unique entries. Commencing network key sync..."
    )
    keys_updated = 0

    for idx, repo in enumerate(deduplicated_repos, start=1):
        print(
            f"    [{idx}/{len(deduplicated_repos)}] Syncing details: '{repo['name']}'...",
            end="",
            flush=True,
        )

        online, live_key = query_signing_fingerprint(repo["address"])

        if online:
            if live_key and live_key.lower() != repo["pubkey"].lower():
                print(" KEY ROTATED")
                print(f"        [-] Outdated Token: {repo['pubkey'][:12]}...")
                print(f"        [+] Synchronized:   {live_key[:12]}...")
                repo["pubkey"] = live_key
                keys_updated += 1
            else:
                print(" OK")
        else:
            print(" UNREACHABLE (Skipping key validation)")

    # Render optimized layouts directly back to the filesystem target
    final_xml = compile_optimized_xml(deduplicated_repos)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(final_xml)

    print(f"\n[+] Pipeline execution completed successfully.")
    print(f"    - Total Unique Repositories Retained: {len(deduplicated_repos)}")
    print(f"    - Cryptographic Keys Automatically Rotated: {keys_updated}")
    print(f"    - Output Manifest Saved: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Deduplicate F-Droid lists by canonical address routes and synchronize signing certificates."
    )
    parser.add_argument(
        "input_xml", help="Path to your masterlist XML data profile"
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Target output for validated files (Default: Overwrites source file context)",
    )

    args = parser.parse_args()
    out_target = args.output if args.output else args.input_xml

    if not os.path.isfile(args.input_xml):
        print(f"Error: Target path '{args.input_xml}' not found.", file=sys.stderr)
        sys.exit(1)

    run_maintenance_pipeline(args.input_xml, out_target)


if __name__ == "__main__":
    main()