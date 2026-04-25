import os
import bpy
import sys
import typing
import inspect
import pkgutil
import importlib
from pathlib import Path
from .logger import get_logger

logger = get_logger()

__all__ = (
    "init",
    "register",
    "unregister",
)

modules = None
ordered_classes = None

def init():
    global modules
    global ordered_classes

    logger.debug("Initializing auto_load...")
    modules = get_all_submodules(Path(__file__).parent.parent)
    ordered_classes = get_ordered_classes_to_register(modules)
    logger.debug(f"Found {len(ordered_classes)} classes to register automatically.")

def register():
    if not ordered_classes:
        init()
        
    for cls in ordered_classes:
        try:
            bpy.utils.register_class(cls)
        except ValueError:
            try:
                bpy.utils.unregister_class(cls)
                bpy.utils.register_class(cls)
            except Exception as e:
                logger.error(f"Failed to re-register class {cls.__name__}: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"Failed to auto-register class {cls.__name__}: {e}", exc_info=True)

    for module in modules:
        if module.__name__ == __name__:
            continue
        if hasattr(module, "register"):
            try:
                module.register()
            except Exception as e:
                logger.error(f"Failed to run register() in {module.__name__}: {e}", exc_info=True)

def unregister():
    for cls in reversed(ordered_classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception as e:
            logger.debug(f"Failed to auto-unregister class {cls.__name__}: {e}")

    for module in reversed(modules):
        if module.__name__ == __name__:
            continue
        if hasattr(module, "unregister"):
            try:
                module.unregister()
            except Exception as e:
                logger.debug(f"Failed to run unregister() in {module.__name__}: {e}")

# --- Helper Functions ---

def get_all_submodules(directory):
    return list(iter_submodules(directory, directory.name))

def iter_submodules(path, package_name):
    for name in sorted(iter_submodule_names(path)):
        try:
            yield importlib.import_module("." + name, package_name)
        except Exception as e:
            logger.error(f"Failed to import submodule {name}: {e}", exc_info=True)

def iter_submodule_names(path, root=""):
    for _, module_name, is_pkg in pkgutil.iter_modules([str(path)]):
        if is_pkg:
            sub_path = path / module_name
            sub_root = root + module_name + "."
            yield from iter_submodule_names(sub_path, sub_root)
        else:
            yield root + module_name

def get_ordered_classes_to_register(modules):
    return toposort(get_dependencies(get_classes_to_register(modules)))

def get_classes_to_register(modules):
    classes = set()
    for module in modules:
        for cls in iter_classes_in_module(module):
            if is_registerable_class(cls):
                classes.add(cls)
    return classes

def iter_classes_in_module(module):
    for value in module.__dict__.values():
        if inspect.isclass(value) and value.__module__ == module.__name__:
            yield value

def is_registerable_class(cls):
    base_classes = (
        bpy.types.Panel,
        bpy.types.Operator,
        bpy.types.PropertyGroup,
        bpy.types.AddonPreferences,
        bpy.types.Header,
        bpy.types.Menu,
        bpy.types.Node,
        bpy.types.NodeSocket,
        bpy.types.NodeTree,
        bpy.types.UIList,
        bpy.types.RenderEngine,
        bpy.types.Gizmo,
        bpy.types.GizmoGroup,
    )
    return issubclass(cls, base_classes) and cls not in base_classes

def get_dependencies(classes):
    dependencies = {cls: set() for cls in classes}
    for cls in classes:
        for field in typing.get_type_hints(cls).values():
            if hasattr(field, "__args__"):
                for arg in field.__args__:
                    if arg in classes:
                        dependencies[cls].add(arg)
            elif field in classes:
                dependencies[cls].add(field)
    return dependencies

def toposort(dependencies):
    sorted_list = []
    visited = set()
    visiting = set()

    def visit(node):
        if node in visited:
            return
        if node in visiting:
            logger.warning(f"Circular dependency detected involving {node.__name__}")
            return
        
        visiting.add(node)
        for dependency in dependencies.get(node, []):
            visit(dependency)
        visiting.remove(node)
        visited.add(node)
        sorted_list.append(node)

    for node in dependencies.keys():
        visit(node)
        
    return sorted_list
