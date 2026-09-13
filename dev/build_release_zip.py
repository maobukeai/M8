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
        "changelog": (
            f"### M8 全能工具箱 v{version} 发布\n\n"
            "1. 修复 Unity FBX 导出尺寸异常：全面对齐工业级 1.0 尺寸与 FBX_SCALE_ALL 标准，彻底杜绝模型导入 Unity 尺寸暴增 100 倍问题\n"
            "2. 优化保存饼菜单交互：去除 Unity 预设深红报警高亮底色误导，改用规范复选开关与即时状态提示；新增空选择导出防呆保护\n"
            "3. 新增 N 侧边栏子标签全景分类管理器 (N-Panel Organizer)：首创智能指纹识别算法，一键归档杂乱插件面板，并支持 0 延迟无痕瞬时还原\n"
            "4. 深度优化偏好设置大屏布局：支持侧边栏宽度比例自由调节，彻底解决大字体/高分屏下设置项被挤压问题\n"
            "5. 全面升级多语言国际化架构 (i18n)：补充 250+ 核心词条，支持随 Blender 语言自动切换，英文环境下全界面无缝切换"
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

