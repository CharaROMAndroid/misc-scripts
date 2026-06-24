import argparse
import json
import os
import re
import sys


def parse_fdroid_xml_to_dict(xml_path):
    """Reads the master XML file as text and extracts repository information

    using a regex block parser to map items back into structured dictionaries.
    """
    try:
        with open(xml_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        print(f"Error: Could not read file '{xml_path}': {e}", file=sys.stderr)
        sys.exit(1)

    # Extract all comments and <item> values sequentially
    pattern = re.compile(r"(|<item>(.*?)</item>)", re.DOTALL)
    tokens = pattern.findall(content)

    repositories = []
    current_repo_data = []

    for token in tokens:
        full_match, item_text = token
        # We only care about the actual text inside <item> tags for values
        if full_match.startswith("<item>"):
            current_repo_data.append(item_text.strip())

        # Once we hit a complete 7-item F-Droid structural block
        if len(current_repo_data) == 7:
            # Map the positional F-Droid XML items back to JSON keys
            repo_dict = {
                "name": current_repo_data[0],
                "address": current_repo_data[1],
                "description": current_repo_data[2],
                # Fallback to an integer if version string is numbers-only
                "version": (
                    int(current_repo_data[3])
                    if current_repo_data[3].isdigit()
                    else current_repo_data[3]
                ),
                # Convert F-Droid "1"/"0" integer strings back to true booleans
                "enabled": current_repo_data[4] == "1",
                "fingerprint": current_repo_data[6],
            }
            repositories.append(repo_dict)
            current_repo_data = []

    return repositories


def serialize_to_rps(repositories, output_path):
    """Converts the list of dictionaries into Neo Store's unique '>' separated

    JSON format.
    """
    json_blocks = []

    for index, repo in enumerate(repositories, start=1):
        # Reconstruct the Neo Store schema matching your original sample data
        rps_item = {
            "id": index,
            "address": repo["address"],
            "name": repo["name"],
            "description": repo["description"],
            "enabled": repo["enabled"],
            "fingerprint": repo["fingerprint"],
        }

        # Add optional version parameter if it exists or is valid
        if repo.get("version"):
            rps_item["version"] = repo["version"]

        # Minimize whitespace to match native exports
        json_str = json.dumps(rps_item, separators=(",", ":"))
        json_blocks.append(json_str)

    # Join the individual objects explicitly with the Neo Store delimiter
    final_rps_content = ">".join(json_blocks)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(final_rps_content)


def main():
    parser = argparse.ArgumentParser(
        description="Convert a unified F-Droid XML repository list back to a Neo Store .rps backup profile."
    )
    parser.add_argument(
        "input_xml", help="Path to the consolidated master XML file"
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Path for the output .rps file (default: input_filename.rps)",
    )

    args = parser.parse_args()

    if not os.path.isfile(args.input_xml):
        print(
            f"Error: The file '{args.input_xml}' does not exist.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Auto-generate output naming scheme if left blank
    if not args.output:
        base_name, _ = os.path.splitext(args.input_xml)
        args.output = base_name + ".rps"

    print(f"Parsing data from structural manifest: {args.input_xml}...")
    parsed_repos = parse_fdroid_xml_to_dict(args.input_xml)

    if not parsed_repos:
        print(
            "Error: No valid 7-item repository structures found in the target XML.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(
        f"Processing {len(parsed_repos)} structures into standardized schema..."
    )
    serialize_to_rps(parsed_repos, args.output)

    print(f"Success! Master Neo Store backup file written to: {args.output}")


if __name__ == "__main__":
    main()