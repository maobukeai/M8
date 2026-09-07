# M8 项目开发、更新与发版规则规范 (Project Guidelines & Release Rules)

本文档是 M8 Blender 插件开发、更新与发布的**核心执行标准**。任何 AI 智能体或人类维护者在后续修改、迭代或发布新版本时，**必须无条件严格遵循本规则**。

---

## 一、 架构与网络核心铁律 (Core Architectural Invariants)

1. **全面无服务器化 (Serverless / GitHub-Only)**：
   - 更新检测、版本分发与用户反馈**完全基于 GitHub 基础设施**，严禁引入任何私有服务器（如已停用的 `mao.591595.xyz`）、自建 API 域名或硬编码 Token。
   - 更新检测接口固定为：`https://api.github.com/repos/maobukeai/M8/releases/latest`。
   - 反馈与报错统一引导至 GitHub Issues：`https://github.com/maobukeai/M8/issues/new`。
2. **下载域名安全白名单**：
   - `utils/network.py` 中的 `_is_allowed_https_url` 必须放行 `github.com`、`objects.githubusercontent.com`（GitHub Release 附件 CDN 重定向域名）及其所有子域名，严禁移除对 GitHub 官方 CDN 的支持。

---

## 二、 防多版本重复安装铁律 (Anti-Duplicate Installation Rules)

为避免用户在多次安装或更新后出现 `M8 v3.7.8`、`M8 v3.7.9` 多个并存、快捷键冲突、操作符重复注册的现象，必须严格执行：

1. **分发端主包固定命名**：
   - GitHub Release 中必须始终上传**固定命名的 `M8.zip`** 作为主安装包（绝不可仅上传带版本号的压缩包）。
   - 无论用户下载多少次，解压后的目录名永远固定为 `M8`，后一次安装必然直接原地覆盖前一次！
2. **客户端优先匹配**：
   - `check_for_updates_async` 中获取下载直链时，**第一优先级匹配 `name == "m8.zip"`**，未找到时才回退至其他 `.zip`。
3. **安装解压原地原子覆盖**：
   - `install_downloaded_zip` 必须强制将更新内容覆盖到当前插件正在运行的目录（`current_dir`），并在更新完成后自动清理可能残留的临时目录。
4. **保留冲突自检与一键清理**：
   - 首选项面板必须常驻旧版本扫描逻辑（`scan_duplicate_installations`），一旦发现 `M8-v*` 等历史残留文件夹，提供一键清理按钮（`m8.clean_duplicate_addons`）。

---

## 三、 标准版本发布工作流 (Release SOP Checklist)

当需要发布新版本时，必须按以下 6 个步骤依序执行，严禁跳步：

### 步骤 1：同步更新版本号
必须同时修改以下两处版本号，保持 100% 一致：
- [`blender_manifest.toml`](file:///blender_manifest.toml): `version = "X.Y.Z"`
- [`__init__.py`](file:///blender_manifest.toml): `bl_info["version"] = (X, Y, Z)`

### 步骤 2：前置自动化验证
在打包前必须运行并通过以下两项本地测试：
```bash
# 1. 语法与编译检查（必须 0 错误）
python _syntax_check.py

# 2. GitHub 更新、白名单与防重复扫描自测（必须全部 PASS）
python dev/selftest_github_update.py
```

### 步骤 3：执行标准打包
运行构建脚本生成标准的防重复主安装包与版本归档包：
```bash
python dev/build_release_zip.py
```
* 构建脚本会自动输出：
  - `dist/M8.zip`（用于覆盖更新的标准主包）
  - `dist/M8-vX.Y.Z.zip`（版本归档包）

### 步骤 4：Git 提交并推送
```bash
git add -A
git commit -m "chore(release): bump version to X.Y.Z"
git push origin main
```

### 步骤 5：发布 GitHub Release 并上传资产
利用 GitHub CLI 或 GitHub 页面创建 Release：
```bash
# 获取文件 SHA-256
$hash = (Get-FileHash dist/M8.zip -Algorithm SHA256).Hash.ToLower()

# 创建 Release 并上传两份资产
gh release create vX.Y.Z dist/M8.zip dist/M8-vX.Y.Z.zip `
  --title "M8 vX.Y.Z" `
  --notes "Release notes...`n`nSHA256: $hash"
```

### 步骤 6：线上检测验证
调用接口核验更新链路是否就绪：
```bash
python -c "import urllib.request, json; print(json.loads(urllib.request.urlopen(urllib.request.Request('https://api.github.com/repos/maobukeai/M8/releases/latest', headers={'User-Agent': 'Blender-M8-Client'})).read())['tag_name'])"
```
确认返回的最新标签为 `vX.Y.Z` 且 assets 中包含 `M8.zip`，发版即告成功！
