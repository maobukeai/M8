import bpy

from ...utils.i18n import _T

class M8_OT_CheckUpdate(bpy.types.Operator):
    bl_idname = "m8.check_update"
    bl_label = _T("检测更新")
    bl_description = _T("检测 M8 全能工具箱在 GitHub 的最新 Release 版本")
    bl_options = {'INTERNAL'}

    def execute(self, context):
        from ...utils.network import check_for_updates_async
        check_for_updates_async(is_manual=True)
        self.report({'INFO'}, _T("正在连接 GitHub 检测更新，请稍候..."))
        return {'FINISHED'}

class M8_OT_SubmitFeedback(bpy.types.Operator):
    bl_idname = "m8.submit_feedback"
    bl_label = _T("提交反馈")
    bl_description = _T("前往 GitHub Issues 提交您的意见、建议或反馈 BUG")
    bl_options = {'INTERNAL'}

    def execute(self, context):
        from ...utils.network import GITHUB_ISSUES_URL
        bpy.ops.wm.url_open(url=GITHUB_ISSUES_URL)
        self.report({'INFO'}, _T("已在浏览器打开 GitHub Issues 页面，欢迎提交建议或反馈！"))
        return {'FINISHED'}

class M8_OT_InstallUpdate(bpy.types.Operator):
    bl_idname = "m8.install_update"
    bl_label = _T("一键更新")
    bl_description = _T("自动下载并安装线上最新版本的 M8 工具箱")
    bl_options = {'INTERNAL'}

    def execute(self, context):
        from ...utils.network import download_and_install_update_async
        download_and_install_update_async()
        self.report({'INFO'}, _T("正在开始下载更新，请稍候..."))
        return {'FINISHED'}

class M8_OT_TriggerTestError(bpy.types.Operator):
    bl_idname = "m8.trigger_test_error"
    bl_label = _T("触发测试错误")
    bl_description = _T("制造一个Bug以测试自动发送错误报告是否正常工作")
    bl_options = {'INTERNAL'}

    def execute(self, context):
        raise ValueError(_T("这是一个测试自动发送错误报告的Bug (M8 Test Bug)"))

class M8_OT_CleanDuplicateAddons(bpy.types.Operator):
    bl_idname = "m8.clean_duplicate_addons"
    bl_label = _T("一键清理旧版残留")
    bl_description = _T("安全扫描并删除可能导致冲突的旧版 M8 文件夹")
    bl_options = {'INTERNAL'}

    def execute(self, context):
        from ...utils.network import remove_duplicate_installations
        removed, errors = remove_duplicate_installations()
        if removed:
            self.report({'INFO'}, _T("已成功清理历史残留目录: ") + ", ".join(removed))
            def draw_done(self, ctx):
                self.layout.label(text=_T("已成功清理以下历史残留版本:"), icon="CHECKMARK")
                for name in removed:
                    self.layout.label(text=f"• {name}")
                if errors:
                    self.layout.separator()
                    self.layout.label(text=_T("部分目录清理失败（可能被占用）:"), icon="ERROR")
                    for err in errors:
                        self.layout.label(text=f"• {err}")
            context.window_manager.popup_menu(draw_done, title=_T("清理结果"), icon="CHECKMARK")
        elif errors:
            self.report({'ERROR'}, _T("清理失败: ") + "; ".join(errors))
        else:
            self.report({'INFO'}, _T("未发现多余的历史旧版本残留。"))
        return {'FINISHED'}

class M8_OT_ShowUpdateDialog(bpy.types.Operator):
    bl_idname = "m8.show_update_dialog"
    bl_label = _T("M8 全能工具箱 - 版本更新")
    bl_description = _T("查看 M8 全能工具箱最新版本更新详情与升级选项")
    bl_options = {'INTERNAL'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=500, confirm_text=_T("关闭"))

    def draw(self, context):
        layout = self.layout
        wm = context.window_manager
        m8 = getattr(wm, "m8", None)
        if not m8:
            layout.label(text=_T("未找到更新状态数据"), icon="ERROR")
            return

        from ...utils.network import get_addon_version, version_tuple_to_str
        cur_ver = version_tuple_to_str(get_addon_version())

        # Header Box
        header_box = layout.box()
        h_row = header_box.row(align=True)
        if m8.update_available:
            h_row.label(text=_T("🎉 发现新版本可用！"), icon="INFO")
        else:
            h_row.label(text=_T("✨ 当前已是最新版本"), icon="CHECKMARK")

        v_row = header_box.row(align=True)
        v_row.label(text=f"{_T('当前版本')}: v{cur_ver}", icon="DESKTOP")
        v_row.label(text=f"➔   {_T('最新版本')}: v{m8.update_version or cur_ver}", icon="FILE_REFRESH")

        if m8.update_available:
            layout.separator(factor=0.5)
            layout.label(text=_T("更新日志 / 新特性:"), icon="TEXT")
            
            box = layout.box()
            changelog_text = m8.update_changelog or _T("无详细更新日志，请前往 GitHub Release 页面查看。")
            lines = [l.strip() for l in changelog_text.split("\n") if l.strip()]
            for line in lines[:10]:
                box.label(text=line[:80])
            if len(lines) > 10:
                box.label(text=_T("...更多详细说明请查看 GitHub Release 页面"))

            layout.separator(factor=0.8)

            if m8.update_status == "updating":
                update_col = layout.column(align=True)
                update_col.scale_y = 1.3
                update_col.label(text=_T("正在下载并覆盖安装，请稍候..."), icon="FILE_REFRESH")
            else:
                act_row = layout.row(align=True)
                act_row.scale_y = 1.3
                
                is_zip = bool(m8.update_download_url and (m8.update_download_url.lower().endswith(".zip") or "/download/" in m8.update_download_url))
                if is_zip:
                    act_row.operator("m8.install_update", text=_T("立即一键更新"), icon="FILE_REFRESH")
                
                op = act_row.operator("wm.url_open", text=_T("浏览器下载") if is_zip else _T("前往 Release 页面"), icon="IMPORT")
                op.url = m8.update_download_url or "https://github.com/maobukeai/M8/releases/latest"
        else:
            layout.separator(factor=0.5)
            layout.label(text=_T("您当前使用的是最新稳定版，无需更新。"), icon="CHECKMARK")
            row = layout.row(align=True)
            row.scale_y = 1.2
            op = row.operator("wm.url_open", text=_T("前往 GitHub 仓库"), icon="WORLD")
            op.url = "https://github.com/maobukeai/M8"

    def execute(self, context):
        return {'FINISHED'}



