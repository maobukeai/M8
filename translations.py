import bpy

# Define translation dictionaries for English (fallback) and Simplified Chinese
# Format must be: {'locale': {(context, 'message'): 'translation', ...}, ...}
translations = {
    "en_US": {
        ("*", "Add Object"): "Add Object",
        ("*", "M8 Toolbox"): "M8 Toolbox",
        ("*", "Settings"): "Settings",
        ("*", "M8 Preferences"): "M8 Preferences",
    },
    "zh_CN": {
        ("*", "Add Object"): "添加对象",
        ("*", "M8 Toolbox"): "M8 工具箱",
        ("*", "Settings"): "设置",
        ("*", "M8 Preferences"): "M8 首选项",
    },
}


def _build_zh_to_en_translations():
    """Build Chinese -> English translation dict from ZH_TO_EN mapping."""
    try:
        from .utils.i18n import ZH_TO_EN
    except Exception:
        return {}

    result = {}
    for zh_src, en_dst in ZH_TO_EN.items():
        if zh_src and en_dst and zh_src != en_dst:
            result[zh_src] = en_dst
    return result


def _get_addon_language():
    """Get the addon language preference. Returns 'EN' or 'ZH'."""
    try:
        import bpy
        root_pkg = ".".join(__package__.split(".")[:3]) if (__package__ or "").startswith("bl_ext") else (__package__ or "").split(".")[0]
        prefs = bpy.context.preferences.addons[root_pkg].preferences
        return getattr(prefs, "addon_language", "ZH")
    except Exception:
        return "ZH"


def _get_blender_locale():
    """Get Blender's current interface locale."""
    try:
        return bpy.app.translations.locale
    except Exception:
        return "en_US"


def register_translations():
    """Register translation tables with Blender's i18n system.

    When addon_language is "EN", register Chinese -> English translations
    under BOTH en_US and the current Blender locale, so that pgettext
    translates Chinese bl_label/bpy.props.name strings to English at display
    time regardless of Blender's interface language.
    """
    # Unregister any previously registered helpers
    unregister_translations()

    # Register the basic static translations
    bpy.app.translations.register(__name__, translations)

    global _en_us_helper, _current_locale_helper

    try:
        from .src.translate.helper import TranslationHelper

        zh_to_en_data = _build_zh_to_en_translations()
        if not zh_to_en_data:
            return

        addon_lang = _get_addon_language()

        if addon_lang == "EN":
            # Always register under en_US
            ti_en = TranslationHelper(f"M8_en_US", zh_to_en_data, lang="en_US")
            ti_en.register()
            _en_us_helper = ti_en

            # Also register under the current Blender locale if it's not en_US
            current_locale = _get_blender_locale()
            if current_locale and current_locale != "en_US":
                ti_cur = TranslationHelper(f"M8_current_locale", zh_to_en_data, lang=current_locale)
                ti_cur.register()
                _current_locale_helper = ti_cur
    except Exception:
        pass


def unregister_translations():
    """Unregister all translation tables."""
    global _en_us_helper, _current_locale_helper

    try:
        bpy.app.translations.unregister(__name__)
    except Exception:
        pass
    try:
        if _en_us_helper is not None:
            _en_us_helper.unregister()
            _en_us_helper = None
    except Exception:
        pass
    try:
        if _current_locale_helper is not None:
            _current_locale_helper.unregister()
            _current_locale_helper = None
    except Exception:
        pass


# Module-level holders for translation helpers
_en_us_helper = None
_current_locale_helper = None
