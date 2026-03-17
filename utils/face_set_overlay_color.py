from functools import cache

import numpy as np

"""

/* Returns the Face Set random color for rendering in the overlay given its ID and a color seed. */
#define GOLDEN_RATIO_CONJUGATE 0.618033988749895f
void BKE_paint_face_set_overlay_color_get(const int face_set, const int seed, uchar r_color[4])
{
  float rgba[4];
  float random_mod_hue = GOLDEN_RATIO_CONJUGATE * (face_set + (seed % 10));
  random_mod_hue = random_mod_hue - floorf(random_mod_hue);
  const float random_mod_sat = BLI_hash_int_01(face_set + seed + 1);
  const float random_mod_val = BLI_hash_int_01(face_set + seed + 2);
  hsv_to_rgb(random_mod_hue,
             0.6f + (random_mod_sat * 0.25f),
             1.0f - (random_mod_val * 0.35f),
             &rgba[0],
             &rgba[1],
             &rgba[2]);
  rgba_float_to_uchar(r_color, rgba);
}

"""


def rot(x, k):
    return (x << k) | (x >> (32 - k))


def final(a, b, c):
    values = np.array([a, b, c], dtype=np.uint32)
    values[2] ^= values[1]
    values[2] -= rot(values[1], 14)
    values[0] ^= values[2]
    values[0] -= rot(values[2], 11)
    values[1] ^= values[0]
    values[1] -= rot(values[0], 25)
    values[2] ^= values[1]
    values[2] -= rot(values[1], 16)
    values[0] ^= values[2]
    values[0] -= rot(values[2], 4)
    values[1] ^= values[0]
    values[1] -= rot(values[0], 14)
    values[2] ^= values[1]
    values[2] -= rot(values[1], 24)
    return values[2]


def bli_hash_int_2d(kx, ky):
    a = b = c = 0xdeadbeef + (2 << 2) + 13
    a += kx
    b += ky
    c = final(a, b, c)
    return c


def bli_hash_int_01(k):
    a = bli_hash_int_2d(k, 0)
    b = (1 / 4294967295)
    return a * b


GOLDEN_RATIO_CONJUGATE = 0.618033988749895


@cache
def bke_paint_face_set_overlay_color_get(face_set, seed):
    from .color import hsv_to_rgb
    v = (face_set + (seed % 10))
    ar = np.array([v, v, v], dtype=np.float32)
    random_mod_hue = np.array(GOLDEN_RATIO_CONJUGATE, dtype=np.float32) * ar
    random_mod_hue = np.subtract(random_mod_hue, np.floor(random_mod_hue))

    random_mod_sat = bli_hash_int_01(face_set + seed + 1)  # 32位
    random_mod_val = bli_hash_int_01(face_set + seed + 2)
    random_mod_hue[1] = 0.6 + (random_mod_sat * 0.25)
    random_mod_hue[2] = 1.0 - (random_mod_val * 0.35)
    return (
        *hsv_to_rgb(
            random_mod_hue[0],
            random_mod_hue[1],
            random_mod_hue[2],
        ),
        0,
    )


if __name__ == "__main__":
    print(bke_paint_face_set_overlay_color_get(104550, 0))
