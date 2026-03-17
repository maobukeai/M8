import os
from enum import Enum

import bpy


class LibraryType(Enum):
    # 空物体的实例
    INSTANCE_COLLECTION = 0  # 在当前文件下
    INSTANCE_COLLECTION_LINK = 1  # 在其他文件中

    LIBRARY = 11

    OVERRIDE_LIBRARY = 21

    VERTS_INSTANCE = 31
    FACES_INSTANCE = 32

    UNKNOWN = -1

    def __str__(self):
        return self.name.title().replace("_", " ")


class Library:
    type: LibraryType
    filepath: str | None
    path_is_exists: bool
    target: None

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return f"{self.type.name} {self.is_linked} {self.filepath} {self.target}"

    def __init__(self, obj: bpy.types.Object):
        self.filepath = None
        self.target = None
        if obj.instance_collection:
            # 如果是在当前文件下的实例集合, 则不考虑
            if obj.instance_collection.library:
                self.target = obj.instance_collection.library
                self.filepath = self.target.filepath
                self.type = LibraryType.INSTANCE_COLLECTION_LINK
            else:
                self.type = LibraryType.INSTANCE_COLLECTION
        elif obj.library:
            self.type = LibraryType.LIBRARY
            self.target = obj.library
            self.filepath = self.target.filepath
        elif obj.override_library:
            self.type = LibraryType.OVERRIDE_LIBRARY
            self.target = obj.override_library.reference.library
            self.filepath = self.target.filepath
        elif obj.type == "MESH" and obj.children:
            if obj.instance_type == "VERTS":
                self.type = LibraryType.VERTS_INSTANCE
            elif obj.instance_type == "FACES":
                self.type = LibraryType.FACES_INSTANCE
            else:
                self.type = LibraryType.UNKNOWN
        else:
            self.type = LibraryType.UNKNOWN

        if getattr(self, "filepath", False):
            self.path_is_exists = os.path.exists(self.filepath)

    @property
    def is_linked(self) -> bool:
        """是链接到其它文件的"""
        return self.type in [
            LibraryType.INSTANCE_COLLECTION_LINK,
            LibraryType.LIBRARY,
            LibraryType.OVERRIDE_LIBRARY,
        ]
    
    @property
    def is_override_library(self) -> bool:
        """是OVERRIDE_LIBRARY"""
        return self.type == LibraryType.OVERRIDE_LIBRARY

    @property
    def is_instance(self) -> bool:
        """是实例"""
        return self.type != LibraryType.UNKNOWN
