#!/usr/bin/env python3
"""Release automation script for Claim Photo Editor.

Usage:
    python scripts/release.py [major|minor|patch]

This script will:
1. Bump the version in __init__.py
2. Update the version in claim-photo-editor.spec
3. Create a git commit with the version bump
4. Create a git tag
5. Push the commit and tag to trigger CI/CD
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path


def get_current_version() -> str:
    """Read the current version from __init__.py."""
    init_file = Path("src/claim_photo_editor/__init__.py")
    content = init_file.read_text()
    match = re.search(r'__version__\s*=\s*"([^"]+)"', content)
    if not match:
        raise ValueError("Could not find version in __init__.py")
    return match.group(1)


def bump_version(current: str, bump_type: str) -> str:
    """Calculate the new version based on bump type."""
    parts = current.split(".")
    if len(parts) != 3:
        raise ValueError(f"Invalid version format: {current}")

    major, minor, patch = map(int, parts)

    if bump_type == "major":
        major += 1
        minor = 0
        patch = 0
    elif bump_type == "minor":
        minor += 1
        patch = 0
    elif bump_type == "patch":
        patch += 1
    else:
        raise ValueError(f"Invalid bump type: {bump_type}")

    return f"{major}.{minor}.{patch}"


def update_version_in_file(file_path: Path, old_version: str, new_version: str) -> None:
    """Update version string in a file."""
    content = file_path.read_text()
    updated = content.replace(f'"{old_version}"', f'"{new_version}"')
    updated = updated.replace(f"'{old_version}'", f"'{new_version}'")
    file_path.write_text(updated)


def run_command(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run a shell command."""
    print(f"Running: {' '.join(cmd)}")
    return subprocess.run(cmd, check=check, capture_output=True, text=True)


def main() -> int:
    """Run the release process."""
    parser = argparse.ArgumentParser(description="Release a new version")
    parser.add_argument(
        "bump_type",
        choices=["major", "minor", "patch"],
        help="Type of version bump",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    args = parser.parse_args()

    # Ensure we're in the project root
    if not Path("src/claim_photo_editor/__init__.py").exists():
        print("Error: Must run from project root directory")
        return 1

    # Check for clean git state
    result = run_command(["git", "status", "--porcelain"], check=False)
    if result.stdout.strip():
        print("Error: Working directory is not clean. Commit or stash changes first.")
        return 1

    # Get current version
    current_version = get_current_version()
    new_version = bump_version(current_version, args.bump_type)

    print(f"Current version: {current_version}")
    print(f"New version: {new_version}")

    if args.dry_run:
        print("\nDry run - no changes made")
        return 0

    # Confirm
    confirm = input(f"\nProceed with release v{new_version}? [y/N] ")
    if confirm.lower() != "y":
        print("Aborted")
        return 1

    # Update version in files
    files_to_update = [
        Path("src/claim_photo_editor/__init__.py"),
        Path("claim-photo-editor.spec"),
    ]

    for file_path in files_to_update:
        if file_path.exists():
            print(f"Updating {file_path}")
            update_version_in_file(file_path, current_version, new_version)

    # Git commit
    run_command(["git", "add", "-A"])
    run_command(["git", "commit", "-m", f"Release v{new_version}"])

    # Git tag
    run_command(["git", "tag", "-a", f"v{new_version}", "-m", f"Release v{new_version}"])

    # Push
    print("\nPushing to remote...")
    run_command(["git", "push"])
    run_command(["git", "push", "--tags"])

    print(f"\nSuccessfully released v{new_version}!")
    print("GitHub Actions will now build and create the release.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
