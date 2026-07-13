import threading
import urllib.request
import urllib.parse
import json
import hashlib
import os
import re
import tomllib
from pathlib import Path
import shutil
import tempfile
import uuid
import zipfile
import bpy
import sys
from .i18n import _T

PLUGIN_TOKEN  = "plg_362d15e623a7466ab4b1dfd0312df224"
CHECK_URL     = "https://mao.591595.xyz/api/plugins/client/check-update"
FEEDBACK_URL  = "https://mao.591595.xyz/api/plugins/client/feedback"

ALLOWED_UPDATE_HOSTS = {"mao.591595.xyz"}
MAX_UPDATE_BYTES = 100 * 1024 * 1024
MAX_ARCHIVE_FILES = 2_000
MAX_EXTRACTED_BYTES = 500 * 1024 * 1024

_update_result = None
_update_lock = threading.Lock()
_reporting_error = False


def _request_headers(content_type=None):
    """Keep the client token out of URLs and request bodies."""
    headers = {
        "User-Agent": "Blender-M8-Client",
        "X-Developer-Token": PLUGIN_TOKEN,
    }
    if content_type:
        headers["Content-Type"] = content_type
    return headers


def _is_allowed_https_url(url):
    try:
        parsed = urllib.parse.urlparse(url)
        return parsed.scheme == "https" and parsed.hostname in ALLOWED_UPDATE_HOSTS
    except Exception:
        return False


def _is_sha256(value):
    if not isinstance(value, str) or len(value) != 64:
        return False
    try:
        int(value, 16)
        return True
    except ValueError:
        return False


def _safe_extract_archive(zip_path, destination):
    """Validate archive paths and size before extracting any update files."""
    destination = Path(destination).resolve()
    with zipfile.ZipFile(zip_path, "r") as archive:
        members = archive.infolist()
        if not members or len(members) > MAX_ARCHIVE_FILES:
            raise ValueError("Update archive has an invalid number of files")
        if sum(member.file_size for member in members) > MAX_EXTRACTED_BYTES:
            raise ValueError("Update archive is too large")

        for member in members:
            target = (destination / member.filename).resolve()
            if target != destination and destination not in target.parents:
                raise ValueError(f"Unsafe path in update archive: {member.filename}")
            if (member.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError(f"Symbolic links are not allowed in update archives: {member.filename}")

        archive.extractall(destination)


def _find_extension_root(extraction_dir):
    extraction_dir = Path(extraction_dir).resolve()
    contents = list(extraction_dir.iterdir())
    root = contents[0] if len(contents) == 1 and contents[0].is_dir() else extraction_dir
    manifest = root / "blender_manifest.toml"
    if not manifest.is_file():
        raise ValueError("Update archive does not contain blender_manifest.toml")
    manifest_data = tomllib.loads(manifest.read_text(encoding="utf-8"))
    if manifest_data.get("id") != "M8" or manifest_data.get("type") != "add-on":
        raise ValueError("Update archive is not an M8 extension")
    return root


def _download_update_archive(url, destination, expected_sha256):
    if not _is_allowed_https_url(url):
        raise ValueError("Update URL must use HTTPS and an approved host")
    if not _is_sha256(expected_sha256):
        raise ValueError("Update server did not provide a valid SHA-256 checksum")

    digest = hashlib.sha256()
    total = 0
    request = urllib.request.Request(url, headers=_request_headers())
    with urllib.request.urlopen(request, timeout=60) as response, open(destination, "wb") as output:
        if not _is_allowed_https_url(response.geturl()):
            raise ValueError("Update redirect left the approved HTTPS host")
        content_length = response.headers.get("Content-Length")
        if content_length and int(content_length) > MAX_UPDATE_BYTES:
            raise ValueError("Update download is too large")
        while chunk := response.read(1024 * 1024):
            total += len(chunk)
            if total > MAX_UPDATE_BYTES:
                raise ValueError("Update download is too large")
            digest.update(chunk)
            output.write(chunk)

    if digest.hexdigest().lower() != expected_sha256.lower():
        raise ValueError("Update checksum verification failed")


def sanitize_error_report(content):
    """Remove common local-path identifiers and cap telemetry payload size."""
    content = re.sub(r"[A-Za-z]:\\Users\\[^\\/\r\n]+", r"<windows-user>", content)
    content = re.sub(r"/home/[^/\r\n]+", r"<unix-user>", content)
    content = re.sub(r'File "[^"]+"', 'File "<local path>"', content)
    return content[:8_000]

def version_tuple_to_str(v):
    if not v:
        return "0.0.0"
    return ".".join(str(x) for x in v)

def get_addon_version():
    # 1. Try to read version from blender_manifest.toml (source of truth for Blender 4.2+ extensions)
    try:
        import os
        import re
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        manifest_path = os.path.join(root, "blender_manifest.toml")
        if os.path.exists(manifest_path):
            with open(manifest_path, "r", encoding="utf-8") as f:
                content = f.read()
                match = re.search(r'^version\s*=\s*["\']([^"\']+)["\']', content, re.MULTILINE)
                if match:
                    return tuple(int(x) for x in match.group(1).split("."))
    except Exception:
        pass

    # 2. Try importing bl_info from parent package
    try:
        from .. import bl_info
        if bl_info and "version" in bl_info:
            return bl_info["version"]
    except Exception:
        pass

    # 3. Fallback to sys.modules traversal
    try:
        pkg = __package__.split('.')
        for i in range(len(pkg), 0, -1):
            parent_pkg = ".".join(pkg[:i])
            module = sys.modules.get(parent_pkg)
            if module and hasattr(module, "bl_info"):
                return module.bl_info.get("version", (3, 5, 0))
    except Exception:
        pass

    return (3, 5, 0)

def _draw_update_dialog(self, context):
    from .i18n import _T
    layout = self.layout
    wm = context.window_manager
    m8 = getattr(wm, "m8", None)
    if not m8:
        return

    cur_ver = version_tuple_to_str(get_addon_version())
    layout.label(text=_T("M8 全能工具箱发现新版本！") if m8.update_available else _T("已经是最新版本"), icon="INFO")
    layout.label(text=f"{_T('当前版本: ')}v{cur_ver}  ->  {_T('最新版本: ')}v{m8.update_version}")
    
    if m8.update_available:
        layout.separator()
        layout.label(text=_T("更新日志:"))
        box = layout.box()
        # Draw changelog line by line
        lines = m8.update_changelog.split('\n')
        for line in lines:
            if line.strip():
                box.label(text=line)
        layout.separator()
        
        if m8.update_status == "updating":
            layout.label(text=_T("正在下载并安装更新，请稍候..."), icon="FILE_REFRESH")
        else:
            row = layout.row(align=True)
            row.operator("m8.install_update", text=_T("一键更新"), icon="FILE_REFRESH")
            op = row.operator("wm.url_open", text=_T("浏览器下载"), icon="IMPORT")
            op.url = m8.update_download_url

def _apply_update_results(is_manual):
    global _update_result
    with _update_lock:
        if _update_result is None:
            return 0.1  # Poll again in 0.1s
        res = _update_result
        _update_result = None

    wm = bpy.context.window_manager
    if not wm:
        return 0.5
    m8 = getattr(wm, "m8", None)
    if not m8:
        return 0.5

    if "error" in res:
        m8.update_status = "error"
        m8.update_available = False
        m8.update_checked = True
        if is_manual:
            def draw_err(self, context):
                self.layout.label(text=res["error"], icon="ERROR")
            wm.popup_menu(draw_err, title=_T("连接失败，请检查网络"), icon="ERROR")
        return None

    m8.update_status = "available" if res.get("updateAvailable") else "latest"
    m8.update_available = bool(res.get("updateAvailable"))
    m8.update_version = res.get("latestVersion", "")
    m8.update_changelog = res.get("changelog", "")
    download_url = res.get("downloadUrl", "") or ""
    update_sha256 = res.get("sha256", res.get("downloadSha256", "")) or ""
    if m8.update_available and (not _is_allowed_https_url(download_url) or not _is_sha256(update_sha256)):
        m8.update_status = "error"
        m8.update_available = False
        m8.update_checked = True
        if is_manual:
            wm.popup_menu(
                lambda self, context: self.layout.label(text="Update metadata failed security validation", icon="ERROR"),
                title="Update check failed",
                icon="ERROR",
            )
        return None
    m8.update_download_url = download_url
    m8.update_sha256 = update_sha256
    m8.update_checked = True

    if m8.update_available:
        # Auto-pop dialog on startup OR on manual check
        wm.popup_menu(_draw_update_dialog, title=_T("检测到新版本"), icon="INFO")
    elif is_manual:
        # Manual check shows "already latest" dialog
        wm.popup_menu(_draw_update_dialog, title=_T("提示"), icon="INFO")

    return None

def check_for_updates_async(is_manual=False):
    global _update_result
    with _update_lock:
        _update_result = None

    wm = bpy.context.window_manager
    m8 = getattr(wm, "m8", None)
    if m8:
        m8.update_status = "checking"

    # Register safety poll timer on main thread BEFORE starting background thread
    bpy.app.timers.register(lambda: _apply_update_results(is_manual))

    def run():
        global _update_result
        try:
            ver_str = version_tuple_to_str(get_addon_version())
            url = f"{CHECK_URL}?{urllib.parse.urlencode({'version': ver_str})}"
            req = urllib.request.Request(url, headers=_request_headers())
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))
            
            with _update_lock:
                _update_result = {
                    "updateAvailable": data.get("updateAvailable", False),
                    "latestVersion": data.get("latestVersion", ""),
                    "downloadUrl": data.get("downloadUrl", ""),
                    "sha256": data.get("sha256", data.get("downloadSha256", "")),
                    "changelog": data.get("changelog", _T("暂无更新日志")),
                }
        except Exception as e:
            with _update_lock:
                _update_result = {"error": str(e)}

    threading.Thread(target=run, daemon=True).start()

def send_feedback_async(feedback_type, content, callback=None):
    feedback_res = None
    feedback_lock = threading.Lock()

    def apply_feedback():
        nonlocal feedback_res
        with feedback_lock:
            if feedback_res is None:
                return 0.1
            success, msg = feedback_res
        
        if callback:
            callback(success, msg)
        return None

    if callback:
        bpy.app.timers.register(apply_feedback)

    def run():
        nonlocal feedback_res
        success = False
        msg = ""
        try:
            ver_str = version_tuple_to_str(get_addon_version())
            payload = {
                "clientVersion": ver_str,
                "feedbackType": feedback_type,
                "content": content
            }
            data_bytes = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(
                FEEDBACK_URL,
                data=data_bytes,
                headers=_request_headers('application/json'),
                method='POST'
            )
            with urllib.request.urlopen(req, timeout=15) as response:
                res_data = json.loads(response.read().decode('utf-8'))
            success = res_data.get("success", False) or "feedback" in res_data
        except Exception as e:
            success = False
            msg = str(e)

        with feedback_lock:
            feedback_res = (success, msg)

    threading.Thread(target=run, daemon=True).start()

def send_feedback_sync_silent(feedback_type, content):
    try:
        ver_str = version_tuple_to_str(get_addon_version())
        payload = {
            "clientVersion": ver_str,
            "feedbackType": feedback_type,
            "content": content
        }
        data_bytes = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(
            FEEDBACK_URL,
            data=data_bytes,
            headers=_request_headers('application/json'),
            method='POST'
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            response.read()
    except Exception:
        pass

def send_error_report_background(content):
    global _reporting_error
    if _reporting_error:
        return
    
    def run():
        global _reporting_error
        _reporting_error = True
        try:
            send_feedback_sync_silent("BUG", sanitize_error_report(content))
        except Exception:
            pass
        finally:
            _reporting_error = False

    threading.Thread(target=run, daemon=True).start()

_install_result = None
_install_lock = threading.Lock()

def _apply_install_results():
    global _install_result
    with _install_lock:
        if _install_result is None:
            return 0.1  # Poll again in 0.1s
        res = _install_result
        _install_result = None

    if "zip_path" in res:
        zip_path = res["zip_path"]
        try:
            if not install_downloaded_zip(zip_path):
                raise RuntimeError("Update installer reported failure")
            res = {"success": True}
        except Exception as exc:
            res = {"error": str(exc)}
        finally:
            try:
                Path(zip_path).unlink(missing_ok=True)
            except Exception:
                pass

    wm = bpy.context.window_manager
    m8 = getattr(wm, "m8", None)
    if m8:
        m8.update_status = "idle"

    if "error" in res:
        def draw_err(self, context):
            self.layout.label(text=res["error"], icon="ERROR")
        wm.popup_menu(draw_err, title=_T("一键更新失败，请尝试手动下载"), icon="ERROR")
        return None

    # Success!
    def draw_ok(self, context):
        self.layout.label(text=_T("更新成功！请重启 Blender 或重新启用插件以应用新版本。"), icon="CHECKMARK")
    wm.popup_menu(draw_ok, title=_T("提示"), icon="CHECKMARK")
    return None

def download_and_install_update_async():
    global _install_result
    with _install_lock:
        _install_result = None

    wm = bpy.context.window_manager
    m8 = getattr(wm, "m8", None)
    if m8:
        m8.update_status = "updating"

    # Register safety poll timer on main thread
    bpy.app.timers.register(_apply_install_results)

    def run():
        global _install_result
        zip_path = None
        try:
            if not m8 or not m8.update_download_url:
                raise Exception(_T("未找到更新下载地址，请先检测更新"))

            with tempfile.NamedTemporaryFile(prefix="M8_update_", suffix=".zip", delete=False) as temp_file:
                zip_path = temp_file.name
            
            print(f"[M8] Downloading update from {m8.update_download_url} to {zip_path}...")
            
            _download_update_archive(m8.update_download_url, zip_path, m8.update_sha256)
            
            # Installation uses bpy.ops and must run on Blender's main thread.
            with _install_lock:
                _install_result = {"zip_path": zip_path}
            zip_path = None
            return

        except Exception as e:
            import traceback
            traceback.print_exc()
            with _install_lock:
                _install_result = {"error": str(e)}
        finally:
            if zip_path:
                Path(zip_path).unlink(missing_ok=True)

    threading.Thread(target=run, daemon=True).start()

def install_downloaded_zip(zip_path):
    # Method 1: If using Blender 4.2+ Extensions system (highly recommended for user_default/M8)
    if hasattr(bpy.ops, "extensions") and hasattr(bpy.ops.extensions, "user_install"):
        try:
            print("[M8] Installing update via Blender Extensions API...")
            bpy.ops.extensions.user_install(filepath=zip_path)
            print("[M8] Update installed successfully via Extensions API.")
            return True
        except Exception as e:
            print(f"[M8] Extensions user_install failed: {e}. Falling back to manual extraction.")

    # Method 2: Manual extraction fallback with a rollback backup.
    try:
        if not zipfile.is_zipfile(zip_path):
            raise ValueError("Downloaded update is not a ZIP archive")

        current_dir = Path(__file__).resolve().parents[1]
        parent_dir = current_dir.parent.resolve()
        addon_name = current_dir.name
        extraction_dir = Path(tempfile.mkdtemp(prefix=f"{addon_name}_update_", dir=parent_dir)).resolve()
        backup_dir = parent_dir / f"{addon_name}_backup_{uuid.uuid4().hex}"

        try:
            _safe_extract_archive(zip_path, extraction_dir)
            source_dir = _find_extension_root(extraction_dir)
            os.replace(current_dir, backup_dir)
            try:
                shutil.move(str(source_dir), str(current_dir))
            except Exception:
                if not current_dir.exists() and backup_dir.exists():
                    os.replace(backup_dir, current_dir)
                raise
        finally:
            if extraction_dir.exists():
                shutil.rmtree(extraction_dir, ignore_errors=True)

        if backup_dir.exists():
            try:
                shutil.rmtree(backup_dir)
            except OSError as cleanup_error:
                print(f"[M8] Update installed, but backup cleanup failed: {cleanup_error}")

        print("[M8] Manual update extraction completed successfully.")
        return True
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise Exception(f"手动更新替换失败: {e}")
