import argparse
import os
import re
import sys
import xml.etree.ElementTree as ET
import requests
from xml.dom import minidom

# Custom network identifier provided by the user
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:140.0) Gecko/20100101 Firefox/140.0 CharaROMFDroidRepoTester/1.0"


def parse_masterlist(xml_path):
    """Parses individual repository item blocks from the input configuration XML."""
    try:
        with open(xml_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        print(f"Error: Could not open manifest file: {e}", file=sys.stderr)
        sys.exit(1)

    # Sequence parser matching 7-item configurations sequential blocks
    pattern = re.compile(r"(|<item>(.*?)</item>)", re.DOTALL)
    tokens = pattern.findall(content)

    repositories = []
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
            repositories.append(repo_struct)
            current_block = []

    return repositories


def query_repository_endpoint(url):
    """Hits the direct verification endpoints of the repository to check status

    and parse structural signatures.
    """
    base_url = url.rstrip("/")
    # Check the standard index-v2 location first
    target_endpoint = f"{base_url}/index-v2.json"
    headers = {"User-Agent": USER_AGENT}

    try:
        # Check availability with a tight 8-second connection timeout window
        response = requests.get(
            target_endpoint, headers=headers, timeout=8, stream=True
        )
        if response.status_code == 200:
            return True, response.headers.get("X-Repo-Signing-Fingerprint", None)

        # Fall back to checking the directory route if modern endpoints return alternative headers
        fallback_endpoint = f"{base_url}/index.xml"
        response = requests.head(
            fallback_endpoint, headers=headers, timeout=5
        )
        if response.status_code == 200:
            return True, None

        return False, None
    except requests.RequestException:
        return False, None


def handle_invalid_repo(repo):
    """Interactive command-line handler to dictate how malformed/dead lines are structured."""
    print(f"\n[!] Connection Failure: '{repo['name']}' ({repo['address']})")
    print("      How would you like to process this dead repository branch?")
    print("      [1] Disable it (Set <item> flag to 0 inside the file)")
    print("      [2] Delete it entirely from the configuration output")
    print("      [3] Comment it out inside the XML array")
    print("      [4] Extract and isolate it to 'invalid_repos.xml'")

    while True:
        choice = input("Enter option (1-4): ").strip()
        if choice in ["1", "2", "3", "4"]:
            return choice
        print("Invalid entry. Please enter a number between 1 and 4.")


def compile_xml_output(repos, commented_repos):
    """Constructs the programmatic raw XML block layers."""
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

    for repo in commented_repos:
        lines.append("        ")

    lines.append("    </string-array>")
    lines.append("</resources>")
    return "\n".join(lines)


def process_tester(input_path, output_path):
    """Main lifecycle process runner for validating the network blocks."""
    repositories = parse_masterlist(input_path)
    print(f"Loaded {len(repositories)} profiles from manifest map. Commencing network verification...")

    valid_output_queue = []
    commented_output_queue = []
    isolated_invalid_queue = []

    for index, repo in enumerate(repositories, start=1):
        print(
            f"[{index}/{len(repositories)}] Checking path: {repo['name']}...",
            end="",
            flush=True,
        )

        is_active, live_fingerprint = query_repository_endpoint(
            repo["address"]
        )

        if is_active:
            print(" ONLINE")
            # Handle certificate generation/rotation updates automatically
            if (
                live_fingerprint
                and live_fingerprint.lower() != repo["pubkey"].lower()
            ):
                print(
                    f"    [*] Key Rotation Detected for {repo['name']}!"
                )
                print(f"        Old: {repo['pubkey'][:10]}...")
                print(f"        New: {live_fingerprint[:10]}...")
                repo["pubkey"] = live_fingerprint

            valid_output_queue.append(repo)

        else:
            print(" OFFLINE/INVALID")
            action = handle_invalid_repo(repo)

            if action == "1":
                # Option 1: Disable repository cleanly
                repo["enabled"] = "0"
                valid_output_queue.append(repo)
            elif action == "2":
                # Option 2: Delete (Do nothing, discard from queue)
                print(f"    [-] Purged '{repo['name']}' profile entries.")
            elif action == "3":
                # Option 3: Move to commented blocks layer
                commented_output_queue.append(repo)
            elif action == "4":
                # Option 4: Move completely out to target separation file
                isolated_invalid_queue.append(repo)

    # Save out primary verified configuration map
    final_master_xml = compile_xml_output(
        valid_output_queue, commented_output_queue
    )
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(final_master_xml)

    # Save out isolation dumps if option 4 was invoked
    if isolated_invalid_queue:
        isolation_file = "invalid_repos.xml"
        invalid_xml_payload = compile_xml_output(isolated_invalid_queue, [])
        with open(isolation_file, "w", encoding="utf-8") as f:
            f.write(invalid_xml_payload)
        print(
            f"[!] Isolate Manifest created: {len(isolated_invalid_queue)} broken profiles routed to '{isolation_file}'"
        )

    print(
        f"\n[+] Execution complete. Active manifest updated at: {output_path}"
    )


def main():
    parser = argparse.ArgumentParser(
        description="Verify and update structural signatures for an F-Droid Masterlist XML profile map."
    )
    parser.add_argument(
        "input_xml", help="Path to your consolidated master XML file"
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Target output for validated entries (Default: overwrites input source)",
    )

    args = parser.parse_args()
    out_destination = args.output if args.output else args.input_xml

    if not os.path.isfile(args.input_xml):
        print(f"Error: File '{args.input_xml}' not found.", file=sys.stderr)
        sys.exit(1)

    process_tester(args.input_xml, out_destination)


if __name__ == "__main__":
    main()