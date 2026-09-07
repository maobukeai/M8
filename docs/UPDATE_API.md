# M8 插件 GitHub Releases 更新与发版指南

M8 现已全面迁移为基于 **GitHub Releases** 的无服务器化更新体系，彻底免除了对自建服务器、域名解析及 API 后端的维护依赖。

---

## 1. 架构与更新原理

- **更新检测接口**：
  - 请求地址：`https://api.github.com/repos/maobukeai/M8/releases/latest`
  - 协议头：`User-Agent: Blender-M8-Client`, `Accept: application/vnd.github+json`
- **版本比对规则**：
  - 从 Release 的 `tag_name`（如 `v3.7.8` 或 `3.7.8`）提取语义化版本号。
  - 与本地 `blender_manifest.toml` 中的 `version` 进行数值比对，若线上版本大于当前安装版本，则触发更新提示。
- **更新安装流程**：
  - 自动从 Release 的 `assets` 列表中寻找 `.zip` 格式的插件包（如 `M8-v3.7.8.zip` 或 `M8.zip`）。
  - 下载到临时目录后，优先调用 Blender 4.2+ 原生扩展安装接口：`bpy.ops.extensions.user_install`；
  - 若调用失败，则自动启用带原子备份与回滚机制的手动解压替换流程。
- **用户反馈与支持**：
  - 插件内的【提交反馈】直接引导打开 GitHub Issues 创建页：`https://github.com/maobukeai/M8/issues/new`。

---

## 2. 维护者日常发布新版本步骤 (Release Checklist)

以后每次发布新版本，无需登录任何服务器，只需三步：

### 第一步：更新本地版本号并推送到 GitHub
1. 修改 `blender_manifest.toml` 中的版本号，例如：
   ```toml
   version = "3.7.8"
   ```
2. 提交并推送到 GitHub 主分支：
   ```bash
   git add blender_manifest.toml
   git commit -m "chore: bump version to 3.7.8"
   git push origin main
   ```

### 第二步：打包插件 ZIP 文件
将包含 `blender_manifest.toml`、`__init__.py` 等插件文件的目录打包成一个 `.zip` 文件，命名推荐为 `M8-v3.7.8.zip`（或者 `M8.zip`）。

> **提示**：确保 ZIP 包的顶层目录可以直接包含 `blender_manifest.toml`，或者顶层为单个 `M8` 文件夹。插件下载器会自动智能识别根目录。

### 第三步：在 GitHub 上创建 Release
1. 打开 GitHub 仓库：[https://github.com/maobukeai/M8/releases](https://github.com/maobukeai/M8/releases)
2. 点击 **"Draft a new release"**。
3. **Tag version**：输入版本标签，推荐格式如 `v3.7.8`（必须以 `v` + 数字版本号，或者直接为数字版本号）。
4. **Release title**：例如 `M8 v3.7.8 - 优化更新与功能更新`。
5. **Attach binaries by dropping them here**：将打包好的 `M8-v3.7.8.zip` 拖入附件上传区域。
6. **Description (更新说明)**：书写清晰的更新日志（Markdown 格式均可，前 10 行将直接展示在用户的 Blender 弹窗中）。
7. 点击 **"Publish release"**。

发布完成后，所有用户的 M8 插件即可自动检测到新版本并一键安装更新！

