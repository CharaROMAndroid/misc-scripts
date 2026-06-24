#!/usr/bin/env python3
import sys
from pathlib import Path

CONFLICT_START = "<<<<<<<"
CONFLICT_MID = "======="
CONFLICT_END = ">>>>>>>"

BASE_BACKUP_DIR = Path.home() / "Documents" / "mergeconflictsolver" / "backups"

def get_project_name(path: Path):
    """
    Try to infer a project folder name from the input path.
    Falls back to 'default'.
    """
    try:
        return path.resolve().parts[-2] if path.is_file() else path.resolve().name
    except Exception:
        return "default"

def resolve_conflict(block, file_path):
    head, incoming = block

    print("\n" + "=" * 80)
    print(f"Conflict found in: {file_path}")
    print("- HEAD (current branch):")
    print(head.strip() or "[empty]")
    print("- Incoming (other branch):")
    print(incoming.strip() or "[empty]")
    print("=" * 80)

    while True:
        choice = input("Keep (h)ead, (i)ncoming, (e)dit, or (s)kip? [h/i/e/s]: ").lower().strip()

        if choice == "h":
            return head
        elif choice == "i":
            return incoming
        elif choice == "s":
            return block[0] + block[1]
        elif choice == "e":
            print("\nEnter replacement content (finish with a single '.' on a line):")
            lines = []
            while True:
                line = input()
                if line == ".":
                    break
                lines.append(line)
            return "\n".join(lines) + "\n"

def process_file(path: Path, project: str):
    content = path.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)

    output = []
    i = 0
    modified = False

    while i < len(content):
        line = content[i]

        if line.startswith(CONFLICT_START):
            modified = True
            head = []
            incoming = []
            i += 1

            while i < len(content) and not content[i].startswith(CONFLICT_MID):
                head.append(content[i])
                i += 1

            i += 1  # skip =======

            while i < len(content) and not content[i].startswith(CONFLICT_END):
                incoming.append(content[i])
                i += 1

            i += 1  # skip >>>>>>>

            resolved = resolve_conflict(
                ("".join(head), "".join(incoming)),
                path
            )
            output.append(resolved)
        else:
            output.append(line)
            i += 1

    if modified:
        backup_dir = BASE_BACKUP_DIR / project
        backup_dir.mkdir(parents=True, exist_ok=True)

        backup_path = backup_dir / path.name

        # avoid overwriting if same filename appears multiple times
        counter = 1
        while backup_path.exists():
            backup_path = backup_dir / f"{path.stem}_{counter}{path.suffix}"
            counter += 1

        backup_path.write_text("".join(content), encoding="utf-8")
        path.write_text("".join(output), encoding="utf-8")

        print(f"\nResolved file written: {path}")
        print(f"Backup stored: {backup_path}")
    else:
        print(f"No conflicts found in {path}")

def main():
    if len(sys.argv) < 2:
        print("Usage: resolve_xml_conflicts.py <file_or_directory>")
        sys.exit(1)

    target = Path(sys.argv[1])

    project = get_project_name(target)

    if target.is_file():
        process_file(target, project)
    else:
        for file in target.rglob("*.xml"):
            process_file(file, project)

if __name__ == "__main__":
    main()