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
    return "3.8.8"
 
EXCLUDE_DIRS = {
    ".git",
    ".github",
    "__pycache__",
    ".pytest_cache",
    ".vscode",
    ".idea",
    "dist",
    "logs",
    "temp",
    ".mission",
    "artifacts",
    "dev",
}

EXCLUDE_EXTENSIONS = {
    ".pyc",
    ".pyo",
    ".zip",
    ".DS_Store",
    ".log",
    ".bak",
    ".fbx",
    ".tmp",
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
        "changelog": (
            f"### M8 全能工具箱 v{version} 发布\n\n"
            "1. 🔒 扩展清单与合规强化：精简 Extension Manifest Tagline 至合规长度，规范声明网络、文件及剪贴板权限与用途说明。\n"
            "2. 🛡️ 网络安全与离线模式遵从：严格校验 HTTPS SSL 证书（拒绝非受信任重试），全面遵从 Blender 离线模式 (online_access=False)。\n"
            "3. 🤖 AI 助手生命周期与健壮性：修复请求异常终止时打字机定时器残留，完善插件卸载/重载/场景切换时的状态隔离与资源注销。\n"
            "4. 📐 Unity FBX 导出缩放修复：移除旧版逆向缩放覆盖，新增 v2 平滑迁移自动纠正历史错误默认值 100.0 并保留用户自定义数值。\n"
            "5. 📦 插件安装与更新流程优化：明确区分用户取消与安装失败状态，避免更新被取消时触发误报或多余回退。\n"
            "6. 🧪 全套回归与自动化质检增强：全套 238 个 Python 文件语法通过，增强对齐、材质、棋盘格、法向与骨骼镜像的自动化断言验证。"
        ),
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

