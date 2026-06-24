import argparse
import os
import re
import sys
from xml.dom import minidom


def extract_items_with_regex(file_path):
    """Reads the file as text and extracts all comments and <item> tags cleanly,

    ignoring root elements like <resources> or <string-array>.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        print(
            f"Warning: Could not read file '{file_path}': {e}", file=sys.stderr
        )
        return []

    # Regex to find either an XML comment <!-- ... --> or an <item>...</item> tag
    pattern = re.compile(r"(<!--.*?-->|<item>.*?</item>)", re.DOTALL)
    tokens = pattern.findall(content)

    repos = []
    current_repo = []
    item_count = 0

    for token in tokens:
        current_repo.append(token)
        if token.startswith("<item>"):
            item_count += 1

        # F-Droid repository structure relies on a strict 7-item block sequence
        if item_count == 7:
            repos.append(current_repo)
            current_repo = []
            item_count = 0

    return repos


def get_repo_address(repo_tokens):
    """Extracts the text inside the second <item> tag to use as a unique deduplication key."""
    item_index = 0
    for token in repo_tokens:
        if token.startswith("<item>"):
            item_index += 1
            if item_index == 2:
                # Strip the tags to isolate the raw URL address string
                match = re.match(r"<item>(.*?)</item>", token, re.DOTALL)
                if match:
                    return match.group(1).strip().lower()
    return ""


def merge_directories_robust(input_dir, output_file):
    """Processes the directory using the regex parser to build the master unified repository XML."""
    seen_addresses = set()
    master_elements = []
    total_merged = 0

    xml_files = sorted(
        [f for f in os.listdir(input_dir) if f.lower().endswith(".xml")]
    )

    if not xml_files:
        print(
            f"Error: No XML files found in directory '{input_dir}'",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Found {len(xml_files)} XML file(s) to process...")

    for file_name in xml_files:
        full_path = os.path.join(input_dir, file_name)

        # Do not accidentally parse our own output destination file
        if os.path.abspath(full_path) == os.path.abspath(output_file):
            continue

        repo_blocks = extract_items_with_regex(full_path)

        for block in repo_blocks:
            address = get_repo_address(block)

            if address in seen_addresses:
                continue

            if address:
                seen_addresses.add(address)

            master_elements.extend(block)
            total_merged += 1

    if total_merged == 0:
        print(
            "Error: No structured 7-item repository sequences could be parsed.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Build the structural XML wrapper string manually
    inner_content = "\n        ".join(master_elements)
    raw_xml_str = f"""<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string-array name="user_repositories">
        {inner_content}
    </string-array>
</resources>"""

    # Use minidom formatting to normalize the output spacing cleanly
    try:
        parsed_xml = minidom.parseString(raw_xml_str)
        pretty_xml = parsed_xml.toprettyxml(indent="    ")
        # Clean up empty formatting lines that minidom injects near comments
        final_xml = "\n".join(
            [line for line in pretty_xml.splitlines() if line.strip()]
        )
    except Exception:
        # Fallback to raw string output if minidom hits unexpected characters
        final_xml = raw_xml_str

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(final_xml)

    print(
        f"Success! Merged {total_merged} unique repositories into: {output_file}"
    )


def main():
    parser = argparse.ArgumentParser(
        description="Robustly combine a directory of F-Droid repository files into a single master layout."
    )
    parser.add_argument(
        "input_dir", help="Directory containing the F-Droid XML files"
    )
    parser.add_argument(
        "-o",
        "--output",
        default="merged_user_repositories.xml",
        help="Path for the output merged XML file (default: merged_user_repositories.xml)",
    )

    args = parser.parse_args()

    if not os.path.isdir(args.input_dir):
        print(
            f"Error: Directory '{args.input_dir}' does not exist.",
            file=sys.stderr,
        )
        sys.exit(1)

    merge_directories_robust(args.input_dir, args.output)


if __name__ == "__main__":
    main()