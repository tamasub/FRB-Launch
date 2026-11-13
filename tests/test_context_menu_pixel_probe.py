"""Independent unit tests for the GUI smoke's color-invariant pixel gate."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from context_menu_pixel_probe import changed_label_pixels

class Color:
    def __init__(self, rgb): self.rgb = rgb
    def red(self): return self.rgb[0]
    def green(self): return self.rgb[1]
    def blue(self): return self.rgb[2]

class Rect:
    def left(self): return 0
    def right(self): return 239
    def top(self): return 12
    def bottom(self): return 50

class Image:
    def __init__(self, w=240, h=60):
        self.w, self.h = w, h
        self.pixels = {}
    def width(self): return self.w
    def height(self): return self.h
    def pixelColor(self, x, y): return Color(self.pixels.get((x, y), (255,255,255)))

def test_diff_detects_colored_or_pale_glyphs_without_dark_rgb_threshold():
    a, b = Image(), Image()
    for y in range(20, 29):
        for x in range(72, 89):
            a.pixels[x,y]=(255,255,255)
            b.pixels[x,y]=(158,180,190)  # lighter than original dark-pixel test
    assert changed_label_pixels(a,b,Rect()) == 17*9

def test_icon_only_change_must_not_count_as_label():
    a, b = Image(), Image()
    for y in range(20, 29):
        for x in range(12, 30):
            b.pixels[x,y]=(255,0,255)
    assert changed_label_pixels(a,b,Rect()) == 0

def test_blank_labels_are_not_accepted():
    a,b=Image(),Image()
    assert changed_label_pixels(a,b,Rect()) == 0

def test_geometry_image_size_change_is_not_accepted():
    assert changed_label_pixels(Image(),Image(241,60),Rect()) == 0
