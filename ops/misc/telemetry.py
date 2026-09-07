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

