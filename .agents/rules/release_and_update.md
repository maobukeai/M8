# M8 插件版本发布与更新标准规则 (Release & Update Rules)

## 核心规则概览
1. **GitHub Releases 驱动**：严禁引入私有自建更新服务器与私有 Token。
2. **防重复安装主包命名**：Release 必须包含固定命名的 `M8.zip` 作为主包，客户端优先下载 `M8.zip`，解压强制原地覆盖。
3. **首选项冲突防护**：保留旧版残留扫描与清理（`m8.clean_duplicate_addons`）。

## 发布检查清单 (Checklist)
1. 修改 `blender_manifest.toml` 与 `__init__.py` 版本号。
2. 执行本地测试：`python _syntax_check.py` 和 `python dev/selftest_github_update.py`。
3. 执行打包：`python dev/build_release_zip.py`。
4. Git 提交并推送：`git add -A && git commit -m "chore(release): bump version to X.Y.Z" && git push origin main`。
5. 发布 Release：`gh release create vX.Y.Z dist/M8.zip dist/M8-vX.Y.Z.zip --title "M8 vX.Y.Z" --notes "..."`。
6. 线上验证：核验 `https://api.github.com/repos/maobukeai/M8/releases/latest`。
