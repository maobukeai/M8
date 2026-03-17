from . import translate, icons

module_list = [
    translate,
    icons,
]


def register():
    for mod in module_list:
        mod.register()


def unregister():
    for mod in module_list:
        mod.unregister()
