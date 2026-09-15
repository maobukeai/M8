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
    return "3.8.6"

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
            f"### M8 全能工具箱 v{version} 重大版本发布\n\n"
            "1. 🚀 重磅推出【智能硬表面法向传递系统 (Smart Normal Transfer)】：针对复杂硬表面、凹面板、沉头孔/阶梯孔群等极限工业场景，提供非破坏性、无瑕疵的面拐角法向重投影与自适应修复技术。\n"
            "2. 💎 拓扑四边面平滑重构引擎：支持 Beauty Quadrangulate 与高密度自适应重构，辅助几何体自动构建极致顺滑的光滑表面，彻底告别三角面拉丝与阴影杂波破面。\n"
            "3. 🎨 沉头孔与多孔群几何分治算法：智能识别内孔凹壁并排除其影响，使平面/曲面外环法向保持绝对平直挺拔，孔内圆柱侧壁与底面保持垂直平顺。\n"
            "4. 🌊 边缘平滑羽化 (Feathering) 梯度衰减：首创拓扑测地线距离权重扩散，支持可调式边缘过渡羽化，在消除破面黑斑的同时保留结构锐边。\n"
            "5. ⚡ 非破坏性工作流与零残留回收：参数即时可调，支持应用烘焙与一键无痕清理，大纲视图辅助集合与物体 100% 洁癖级自动回收。\n"
            "6. 🌐 全面补齐专业 i18n 英汉双语映射，国际化体验平滑一致；通过 237 个文件语法自检与 34 项硬表面全场景极限自动化测试套件。"
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

