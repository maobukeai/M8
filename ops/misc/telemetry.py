import bpy

class M8_OT_CheckUpdate(bpy.types.Operator):
    bl_idname = "m8.check_update"
    bl_label = "检测更新"
    bl_description = "检测 M8 全能工具箱的线上最新版本"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        from ...utils.network import check_for_updates_async
        check_for_updates_async(is_manual=True)
        self.report({'INFO'}, "正在连接服务器检测更新，请稍候...")
        return {'FINISHED'}

class M8_OT_SubmitFeedback(bpy.types.Operator):
    bl_idname = "m8.submit_feedback"
    bl_label = "提交反馈"
    bl_description = "提交您的意见、建议或BUG到开发团队"
    bl_options = {'REGISTER', 'UNDO'}

    feedback_type: bpy.props.EnumProperty(
        name="反馈类型",
        items=[
            ('SUGGESTION', "建议 (Suggestion)", "提交功能建议"),
            ('BUG', "BUG反馈 (Bug)", "提交插件运行出错/缺陷报告")
        ],
        default='SUGGESTION'
    )
    content: bpy.props.StringProperty(
        name="内容",
        description="请简要描述您的建议或遇到的问题（最少5个字）",
        default=""
    )

    def draw(self, context):
        from ...utils.i18n import _T
        layout = self.layout
        layout.prop(self, "feedback_type")
        
        col = layout.column(align=True)
        col.label(text=_T("反馈内容"))
        col.prop(self, "content", text="")

    def invoke(self, context, event):
        self.content = ""
        return context.window_manager.invoke_props_dialog(self, width=400)

    def execute(self, context):
        from ...utils.i18n import _T
        if len(self.content.strip()) < 5:
            self.report({'WARNING'}, _T("内容太短：反馈内容最少为5个字"))
            return {'CANCELLED'}
        
        self.report({'INFO'}, _T("提交中..."))
        
        def feedback_callback(success, msg):
            import bpy
            if success:
                bpy.context.window_manager.popup_menu(
                    lambda self, ctx: self.layout.label(text=_T("反馈提交成功，感谢您的支持！"), icon="CHECKMARK"),
                    title=_T("提示"),
                    icon="CHECKMARK"
                )
            else:
                bpy.context.window_manager.popup_menu(
                    lambda self, ctx: self.layout.label(text=f"{_T('连接失败，请检查网络')}: {msg}", icon="ERROR"),
                    title=_T("提示"),
                    icon="ERROR"
                )

        from ...utils.network import send_feedback_async
        send_feedback_async(self.feedback_type, self.content, callback=feedback_callback)
        return {'FINISHED'}

class M8_OT_InstallUpdate(bpy.types.Operator):
    bl_idname = "m8.install_update"
    bl_label = "一键更新"
    bl_description = "自动下载并安装线上最新版本的 M8 工具箱"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        from ...utils.network import download_and_install_update_async
        download_and_install_update_async()
        self.report({'INFO'}, "正在开始下载更新，请稍候...")
        return {'FINISHED'}
