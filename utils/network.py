import threading
import urllib.request
import urllib.parse
import json
import bpy
import sys
import traceback

PLUGIN_TOKEN  = "plg_362d15e623a7466ab4b1dfd0312df224"
CHECK_URL     = "https://mao.591595.xyz/api/plugins/client/check-update"
FEEDBACK_URL  = "https://mao.591595.xyz/api/plugins/client/feedback"

_update_result = None
_update_lock = threading.Lock()
_reporting_error = False

def version_tuple_to_str(v):
    if not v:
        return "0.0.0"
    return ".".join(str(x) for x in v)

def get_addon_version():
    pkg = __package__.split('.')
    for i in range(len(pkg), 0, -1):
        parent_pkg = ".".join(pkg[:i])
        module = sys.modules.get(parent_pkg)
        if module and hasattr(module, "bl_info"):
            return module.bl_info.get("version", (3, 5, 0))
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
            wm.popup_menu(draw_err, title="连接失败，请检查网络", icon="ERROR")
        return None

    m8.update_status = "available" if res.get("updateAvailable") else "latest"
    m8.update_available = bool(res.get("updateAvailable"))
    m8.update_version = res.get("latestVersion", "")
    m8.update_changelog = res.get("changelog", "")
    m8.update_download_url = res.get("downloadUrl", "") or ""
    m8.update_checked = True

    if m8.update_available:
        # Auto-pop dialog on startup OR on manual check
        wm.popup_menu(_draw_update_dialog, title="检测到新版本", icon="INFO")
    elif is_manual:
        # Manual check shows "already latest" dialog
        wm.popup_menu(_draw_update_dialog, title="提示", icon="INFO")

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
            # Use query parameter or x-developer-token header
            url = f"{CHECK_URL}?token={PLUGIN_TOKEN}&version={ver_str}"
            req = urllib.request.Request(url, headers={'User-Agent': 'Blender-M8-Client'})
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))
            
            with _update_lock:
                _update_result = {
                    "updateAvailable": data.get("updateAvailable", False),
                    "latestVersion": data.get("latestVersion", ""),
                    "downloadUrl": data.get("downloadUrl", ""),
                    "changelog": data.get("changelog", "暂无更新日志"),
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
                "token": PLUGIN_TOKEN,
                "clientVersion": ver_str,
                "feedbackType": feedback_type,
                "content": content
            }
            data_bytes = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(
                FEEDBACK_URL,
                data=data_bytes,
                headers={
                    'Content-Type': 'application/json',
                    'User-Agent': 'Blender-M8-Client',
                    'x-developer-token': PLUGIN_TOKEN
                },
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
            "token": PLUGIN_TOKEN,
            "clientVersion": ver_str,
            "feedbackType": feedback_type,
            "content": content
        }
        data_bytes = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(
            FEEDBACK_URL,
            data=data_bytes,
            headers={
                'Content-Type': 'application/json',
                'User-Agent': 'Blender-M8-Client',
                'x-developer-token': PLUGIN_TOKEN
            },
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
            send_feedback_sync_silent("BUG", content)
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

    wm = bpy.context.window_manager
    m8 = getattr(wm, "m8", None)
    if m8:
        m8.update_status = "idle"

    if "error" in res:
        def draw_err(self, context):
            self.layout.label(text=res["error"], icon="ERROR")
        wm.popup_menu(draw_err, title="一键更新失败，请尝试手动下载", icon="ERROR")
        return None

    # Success!
    def draw_ok(self, context):
        self.layout.label(text="更新成功！请重启 Blender 或重新启用插件以应用新版本。", icon="CHECKMARK")
    wm.popup_menu(draw_ok, title="提示", icon="CHECKMARK")
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
        import tempfile
        import os
        try:
            if not m8 or not m8.update_download_url:
                raise Exception("未找到更新下载地址，请先检测更新")

            # Download to temp file
            temp_dir = tempfile.gettempdir()
            zip_path = os.path.join(temp_dir, "M8_update_temp.zip")
            
            print(f"[M8] Downloading update from {m8.update_download_url} to {zip_path}...")
            
            req = urllib.request.Request(m8.update_download_url, headers={'User-Agent': 'Blender-M8-Client'})
            with urllib.request.urlopen(req, timeout=60) as response, open(zip_path, 'wb') as out_file:
                out_file.write(response.read())
            
            # Install
            success = install_downloaded_zip(zip_path)
            if success:
                with _install_lock:
                    _install_result = {"success": True}
            else:
                raise Exception("安装更新包失败，请尝试手动安装")
        except Exception as e:
            import traceback
            traceback.print_exc()
            with _install_lock:
                _install_result = {"error": str(e)}

    threading.Thread(target=run, daemon=True).start()

def install_downloaded_zip(zip_path):
    import os
    import shutil
    import zipfile
    import bpy

    # Method 1: If using Blender 4.2+ Extensions system (highly recommended for user_default/M8)
    if hasattr(bpy.ops, "extensions") and hasattr(bpy.ops.extensions, "user_install"):
        try:
            print("[M8] Installing update via Blender Extensions API...")
            bpy.ops.extensions.user_install(filepath=zip_path)
            print("[M8] Update installed successfully via Extensions API.")
            return True
        except Exception as e:
            print(f"[M8] Extensions user_install failed: {e}. Falling back to manual extraction.")

    # Method 2: Manual extraction fallback
    try:
        current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        parent_dir = os.path.dirname(current_dir)
        addon_name = os.path.basename(current_dir)

        # Extract to temp dir
        temp_extract_dir = os.path.join(parent_dir, f"{addon_name}_temp_update")
        if os.path.exists(temp_extract_dir):
            shutil.rmtree(temp_extract_dir)
        os.makedirs(temp_extract_dir)

        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(temp_extract_dir)

        # Find src directory inside temp folder
        src_folder = temp_extract_dir
        contents = os.listdir(temp_extract_dir)
        if len(contents) == 1 and os.path.isdir(os.path.join(temp_extract_dir, contents[0])):
            src_folder = os.path.join(temp_extract_dir, contents[0])

        # Rename old dir to avoid write locks on Windows
        old_dir = os.path.join(parent_dir, f"{addon_name}_old")
        if os.path.exists(old_dir):
            try:
                shutil.rmtree(old_dir)
            except Exception:
                pass
        
        os.rename(current_dir, old_dir)

        # Move new extracted folder into place
        shutil.move(src_folder, current_dir)

        # Cleanup temp folders
        try:
            shutil.rmtree(temp_extract_dir)
        except Exception:
            pass

        try:
            shutil.rmtree(old_dir)
        except Exception:
            pass

        print("[M8] Manual update extraction completed successfully.")
        return True
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise Exception(f"手动更新替换失败: {e}")
