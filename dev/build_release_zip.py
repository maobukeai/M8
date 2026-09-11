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

def update_version_json(version, sha256_hash):
    import json
    version_json_path = ROOT / "version.json"
    data = {
        "version": version,
        "name": "M8.zip",
        "download_url": f"https://github.com/maobukeai/M8/releases/download/v{version}/M8.zip",
        "sha256": sha256_hash,
        "changelog": f"M8 全能工具箱 v{version} 发布\n\n1. 新增【全局 UV 棋盘格显示 (UV Checker)】：在 Z 键着色饼菜单顶部集成一键切换视口 UV 棋盘格材质覆盖，内置经典 UV 网格、彩色网格与高对比黑白棋盘 3 种图案，支持实时无缝密度缩放\n2. Z 键着色饼菜单【材质管理】深度重构：新增快速新建材质（自动赋给所选面）、独立材质副本（多用户共享数可视化与一键单用户化）、材质批量赋予至选中物体\n3. 模式联动核心操作：编辑模式支持【指定到所选面】与【选同面】；物体模式支持【选择同材质】与【一键清理空材质槽】\n4. 支持检测并一键清理外部场景全局覆盖材质",
    }
    version_json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[BUILD] Synchronized {version_json_path.name} with v{version}")

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

    # Compute SHA-256
    import hashlib
    h = hashlib.sha256()
    with open(standard_zip, "rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    sha256_hash = h.hexdigest()

    update_version_json(version, sha256_hash)

    size_mb = standard_zip.stat().st_size / (1024 * 1024)
    print(f"[BUILD] Successfully generated:")
    print(f"  -> {standard_zip.name} ({size_mb:.2f} MB, {file_count} files, SHA256: {sha256_hash[:16]}...)")
    print(f"  -> {versioned_zip.name} ({size_mb:.2f} MB, {file_count} files)")
    return standard_zip, versioned_zip

if __name__ == "__main__":
    build_zip()

