"""Build release ZIP for Blender 4.2+ Extension."""
import os
import zipfile
from pathlib import Path

import re
import shutil

ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = ROOT / "dist"
DIST_DIR.mkdir(exist_ok=True)

def get_manifest_version():
    manifest_path = ROOT / "blender_manifest.toml"
    if manifest_path.is_file():
        content = manifest_path.read_text(encoding="utf-8")
        match = re.search(r'^version\s*=\s*["\']([^"\']+)["\']', content, re.MULTILINE)
        if match:
            return match.group(1)
    return "3.7.8"

EXCLUDE_DIRS = {
    ".git",
    ".github",
    "__pycache__",
    ".pytest_cache",
    ".vscode",
    ".idea",
    "dist",
}

EXCLUDE_EXTENSIONS = {
    ".pyc",
    ".pyo",
    ".zip",
    ".DS_Store",
}

def should_exclude(rel_path: Path):
    for part in rel_path.parts:
        if part in EXCLUDE_DIRS:
            return True
    if rel_path.suffix in EXCLUDE_EXTENSIONS:
        return True
    if rel_path.name.startswith("."):
        return True
    return False

def build_zip():
    version = get_manifest_version()
    standard_zip = DIST_DIR / "M8.zip"
    versioned_zip = DIST_DIR / f"M8-v{version}.zip"

    print(f"[BUILD] Packaging M8 v{version}...")
    file_count = 0
    with zipfile.ZipFile(standard_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for root, dirs, files in os.walk(ROOT):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith(".")]
            for file in files:
                full_path = Path(root) / file
                rel_path = full_path.relative_to(ROOT)
                if should_exclude(rel_path):
                    continue
                zf.write(full_path, arcname=str(rel_path))
                file_count += 1

    shutil.copy2(standard_zip, versioned_zip)

    size_mb = standard_zip.stat().st_size / (1024 * 1024)
    print(f"[BUILD] Successfully generated:")
    print(f"  -> {standard_zip.name} ({size_mb:.2f} MB, {file_count} files) [Standard/Anti-duplicate]")
    print(f"  -> {versioned_zip.name} ({size_mb:.2f} MB, {file_count} files) [Versioned Archive]")
    return standard_zip, versioned_zip

if __name__ == "__main__":
    build_zip()

