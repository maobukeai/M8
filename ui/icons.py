import os
import bpy
import bpy.utils.previews

_preview_collection = None
_cache_dir = None


def _addon_cache_dir():
    try:
        path = bpy.utils.user_resource("SCRIPTS", path=os.path.join("M8", "_m8_icon_cache"), create=True)
        if path:
            return path
    except Exception:
        pass
    base = os.path.dirname(__file__)
    return os.path.join(base, "_m8_icon_cache")


def _ensure_cache_dir():
    global _cache_dir
    if _cache_dir is None:
        _cache_dir = _addon_cache_dir()
    os.makedirs(_cache_dir, exist_ok=True)
    return _cache_dir


def _new_image(name, w=32, h=32):
    img = bpy.data.images.new(name=name, width=w, height=h, alpha=True, float_buffer=False)
    img.colorspace_settings.name = "sRGB"
    return img


def _fill(pixels, w, h, rgba):
    r, g, b, a = rgba
    for y in range(h):
        for x in range(w):
            i = (y * w + x) * 4
            pixels[i + 0] = r
            pixels[i + 1] = g
            pixels[i + 2] = b
            pixels[i + 3] = a


def _rect(pixels, w, h, x0, y0, x1, y1, rgba):
    r, g, b, a = rgba
    x0 = max(0, min(w, int(x0)))
    x1 = max(0, min(w, int(x1)))
    y0 = max(0, min(h, int(y0)))
    y1 = max(0, min(h, int(y1)))
    for y in range(y0, y1):
        for x in range(x0, x1):
            i = (y * w + x) * 4
            pixels[i + 0] = r
            pixels[i + 1] = g
            pixels[i + 2] = b
            pixels[i + 3] = a


def _diamond(pixels, w, h, cx, cy, radius, rgba):
    r, g, b, a = rgba
    cx = int(cx)
    cy = int(cy)
    radius = int(radius)
    for y in range(max(0, cy - radius), min(h, cy + radius + 1)):
        for x in range(max(0, cx - radius), min(w, cx + radius + 1)):
            if abs(x - cx) + abs(y - cy) <= radius:
                i = (y * w + x) * 4
                pixels[i + 0] = r
                pixels[i + 1] = g
                pixels[i + 2] = b
                pixels[i + 3] = a


def _arrow(pixels, w, h, direction, fg, bg=None):
    if bg is not None:
        _fill(pixels, w, h, bg)
    margin = 6
    cx = w // 2
    cy = h // 2
    shaft = 3
    head = 9
    if direction == "LEFT":
        _rect(pixels, w, h, margin + head, cy - shaft, w - margin, cy + shaft + 1, fg)
        for k in range(head):
            _rect(pixels, w, h, margin + k, cy - k, margin + k + 1, cy + k + 1, fg)
    elif direction == "RIGHT":
        _rect(pixels, w, h, margin, cy - shaft, w - margin - head, cy + shaft + 1, fg)
        for k in range(head):
            _rect(pixels, w, h, w - margin - k - 1, cy - k, w - margin - k, cy + k + 1, fg)
    elif direction == "UP":
        _rect(pixels, w, h, cx - shaft, margin, cx + shaft + 1, h - margin - head, fg)
        for k in range(head):
            _rect(pixels, w, h, cx - k, h - margin - k - 1, cx + k + 1, h - margin - k, fg)
    else:
        _rect(pixels, w, h, cx - shaft, margin + head, cx + shaft + 1, h - margin, fg)
        for k in range(head):
            _rect(pixels, w, h, cx - k, margin + k, cx + k + 1, margin + k + 1, fg)


def _write_png(img, filepath):
    img.filepath_raw = filepath
    img.file_format = "PNG"
    img.save()


def _build_icon_png(name):
    cache_dir = _ensure_cache_dir()
    filepath = os.path.join(cache_dir, f"{name}.png")
    if os.path.exists(filepath):
        return filepath

    img = _new_image(f"M8Icon_{name}", 32, 32)
    w, h = img.size
    pixels = list(img.pixels[:])

    if name == "open":
        _fill(pixels, w, h, (0.12, 0.52, 0.95, 1.0))
        _rect(pixels, w, h, 7, 9, 26, 25, (1.0, 1.0, 1.0, 0.95))
        _rect(pixels, w, h, 9, 11, 24, 14, (0.12, 0.52, 0.95, 1.0))
        _diamond(pixels, w, h, 16, 16, 6, (1.0, 0.84, 0.0, 0.95))
    elif name == "temp":
        _fill(pixels, w, h, (0.55, 0.18, 0.85, 1.0))
        _rect(pixels, w, h, 12, 6, 20, 26, (1.0, 1.0, 1.0, 0.95))
        _rect(pixels, w, h, 10, 10, 22, 13, (0.2, 0.1, 0.3, 0.5))
        _rect(pixels, w, h, 10, 16, 22, 19, (0.2, 0.1, 0.3, 0.5))
    elif name == "autosave":
        _fill(pixels, w, h, (0.07, 0.72, 0.49, 1.0))
        _diamond(pixels, w, h, 16, 16, 11, (1.0, 1.0, 1.0, 0.95))
        _arrow(pixels, w, h, "DOWN", (0.07, 0.72, 0.49, 1.0))
    elif name == "prefs":
        _fill(pixels, w, h, (0.25, 0.25, 0.25, 1.0))
        _diamond(pixels, w, h, 16, 16, 12, (0.95, 0.95, 0.95, 1.0))
        _diamond(pixels, w, h, 16, 16, 6, (0.25, 0.25, 0.25, 1.0))
        _diamond(pixels, w, h, 16, 16, 3, (1.0, 0.6, 0.1, 1.0))
    elif name == "pack":
        _fill(pixels, w, h, (0.95, 0.55, 0.1, 1.0))
        _rect(pixels, w, h, 8, 10, 24, 25, (0.18, 0.12, 0.08, 0.95))
        _rect(pixels, w, h, 10, 12, 22, 23, (0.95, 0.85, 0.7, 1.0))
        _rect(pixels, w, h, 14, 7, 18, 10, (0.18, 0.12, 0.08, 0.95))
    elif name == "purge":
        _fill(pixels, w, h, (0.9, 0.18, 0.22, 1.0))
        _rect(pixels, w, h, 10, 10, 22, 25, (1.0, 1.0, 1.0, 0.95))
        _rect(pixels, w, h, 12, 8, 20, 10, (1.0, 1.0, 1.0, 0.95))
        _rect(pixels, w, h, 13, 13, 15, 22, (0.9, 0.18, 0.22, 1.0))
        _rect(pixels, w, h, 17, 13, 19, 22, (0.9, 0.18, 0.22, 1.0))
    elif name == "prev":
        _arrow(pixels, w, h, "LEFT", (1.0, 1.0, 1.0, 0.98), (0.1, 0.6, 1.0, 1.0))
    elif name == "next":
        _arrow(pixels, w, h, "RIGHT", (1.0, 1.0, 1.0, 0.98), (0.1, 0.6, 1.0, 1.0))
    elif name == "recent":
        _fill(pixels, w, h, (0.12, 0.12, 0.12, 1.0))
        _diamond(pixels, w, h, 16, 16, 12, (0.2, 0.7, 1.0, 1.0))
        _rect(pixels, w, h, 15, 10, 17, 18, (1.0, 1.0, 1.0, 1.0))
        _rect(pixels, w, h, 16, 16, 22, 18, (1.0, 1.0, 1.0, 1.0))
    elif name == "unity":
        _fill(pixels, w, h, (0.12, 0.74, 0.36, 1.0))
        _diamond(pixels, w, h, 16, 16, 12, (1.0, 1.0, 1.0, 0.98))
        _diamond(pixels, w, h, 16, 16, 7, (0.12, 0.74, 0.36, 1.0))
        _rect(pixels, w, h, 13, 8, 19, 24, (1.0, 1.0, 1.0, 0.98))
        _rect(pixels, w, h, 15, 10, 17, 22, (0.12, 0.74, 0.36, 1.0))
    else:
        _fill(pixels, w, h, (0.5, 0.5, 0.5, 1.0))
        _diamond(pixels, w, h, 16, 16, 10, (1.0, 1.0, 1.0, 0.95))

    img.pixels = pixels
    try:
        _write_png(img, filepath)
    finally:
        try:
            bpy.data.images.remove(img)
        except Exception:
            pass

    return filepath


def _ensure_previews():
    global _preview_collection
    if _preview_collection is None:
        _preview_collection = bpy.utils.previews.new()
    return _preview_collection


def get_icon_id(name):
    name = (name or "").strip().lower()
    if not name:
        return 0
    pcoll = _ensure_previews()
    if name in pcoll:
        try:
            return pcoll[name].icon_id
        except Exception:
            return 0
    try:
        path = _build_icon_png(name)
        pcoll.load(name, path, "IMAGE")
        return pcoll[name].icon_id
    except Exception:
        return 0


def register():
    pcoll = _ensure_previews()
    for name in ("recent", "open", "temp", "autosave", "prefs", "pack", "purge", "prev", "next", "unity"):
        if name in pcoll:
            continue
        try:
            path = _build_icon_png(name)
            pcoll.load(name, path, "IMAGE")
        except Exception:
            pass


def unregister():
    global _preview_collection
    try:
        if _preview_collection is not None:
            bpy.utils.previews.remove(_preview_collection)
    except Exception:
        pass
    _preview_collection = None
