import argparse
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from xml.dom import minidom


def parse_rps_data(raw_data):
    """Parses raw Neo Store .rps string content into a list of dictionaries."""
    # Split individual JSON structures that are separated by '>'
    json_strings = re.split(r">\s*(?={)", raw_data.strip())
    repositories = []

    for item in json_strings:
        if not item.strip():
            continue
        try:
            repo_dict = json.loads(item)
            repositories.append(repo_dict)
        except json.JSONDecodeError as e:
            print(f"Skipping invalid JSON segment: {e}", file=sys.stderr)

    return repositories


def generate_fdroid_xml(repositories):
    """Converts a parsed list of repositories into the F-Droid XML structure."""
    root = ET.Element("resources")
    string_array = ET.SubElement(
        root, "string-array", name="user_repositories"
    )

    for repo in repositories:
        # 1. Name
        string_array.append(ET.Comment(" name "))
        name_item = ET.SubElement(string_array, "item")
        name_item.text = repo.get("name", "")

        # 2. Address
        string_array.append(ET.Comment(" address "))
        address_item = ET.SubElement(string_array, "item")
        address_item.text = repo.get("address", "")

        # 3. Description
        string_array.append(ET.Comment(" description "))
        desc_item = ET.SubElement(string_array, "item")
        desc_item.text = repo.get("description", "")

        # 4. Version
        string_array.append(ET.Comment(" version "))
        version_item = ET.SubElement(string_array, "item")
        version_item.text = str(repo.get("version", "20002"))

        # 5. Enabled
        string_array.append(ET.Comment(" enabled "))
        enabled_item = ET.SubElement(string_array, "item")
        enabled_item.text = "1" if repo.get("enabled", True) else "0"

        # 6. Push Requests
        string_array.append(ET.Comment(" push requests "))
        push_item = ET.SubElement(string_array, "item")
        push_item.text = "ignore"

        # 7. Pubkey
        string_array.append(ET.Comment(" pubkey "))
        pubkey_item = ET.SubElement(string_array, "item")
        pubkey_item.text = repo.get("fingerprint", "")

    xml_str = ET.tostring(root, encoding="utf-8")
    parsed_xml = minidom.parseString(xml_str)
    return parsed_xml.toprettyxml(indent="    ")


def main():
    parser = argparse.ArgumentParser(
        description="Convert Neo Store .rps repository files to F-Droid XML format."
    )
    parser.add_argument(
        "input_file", help="Path to the target .rps file to convert"
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Path for the output XML file (default: input_filename.xml)",
    )

    args = parser.parse_args()

    # Verify input file exists
    if not os.path.isfile(args.input_file):
        print(
            f"Error: The file '{args.input_file}' does not exist.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Determine output path if not specified
    if not args.output:
        base_name, _ = os.path.splitext(args.input_file)
        args.output = base_name + ".xml"

    # Read, parse, and convert
    try:
        with open(args.input_file, "r", encoding="utf-8") as f:
            rps_content = f.read()

        parsed_repos = parse_rps_data(rps_content)

        if not parsed_repos:
            print(
                "Error: No valid repository data found in the file.",
                file=sys.stderr,
            )
            sys.exit(1)

        output_xml = generate_fdroid_xml(parsed_repos)

        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output_xml)

        print(f"Success! Converted data saved to: {args.output}")

    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()