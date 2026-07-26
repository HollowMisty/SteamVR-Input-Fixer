"""gen_assets.py — regenerate the panel textures and icon."""
import math
import os
from PIL import Image, ImageDraw, ImageFont

from fixinput import UPD_RECT, VERSION

HERE = os.path.dirname(os.path.abspath(__file__))
W, H = 800, 500


def fonts():
    try:
        return (ImageFont.truetype("segoeuib.ttf", 56),
                ImageFont.truetype("segoeuib.ttf", 40),
                ImageFont.truetype("segoeui.ttf", 26),
                ImageFont.truetype("segoeui.ttf", 22))
    except OSError:
        f = ImageFont.load_default()
        return f, f, f, f


F_BTN, F_HEAD, F_SMALL, F_TINY = fonts()

# central button rect — mirrored by BTN_* in fixinput.py; keep it vertically
# centered (170+330 == 500) so the hit test survives a mouse-Y flip
BTN = (200, 170, 600, 330)


def panel(btn_fill, btn_label, subtitle, check=False):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # panel chrome — flat, small radius, thin neutral border
    d.rounded_rectangle((6, 6, W - 6, H - 6), radius=14,
                        fill=(22, 24, 29, 255), outline=(52, 58, 70, 255),
                        width=2)
    d.text((32, 38), "SteamVR Input Fixer", font=F_HEAD,
           fill=(240, 244, 255, 255))
    tw = d.textlength("SteamVR Input Fixer", font=F_HEAD)
    d.text((32 + tw + 16, 56), f"v{VERSION}", font=F_TINY,
           fill=(100, 108, 124, 255))
    # the button itself — flat accent, no outline
    d.rounded_rectangle(BTN, radius=10, fill=btn_fill)
    bx = (BTN[0] + BTN[2]) / 2
    by = (BTN[1] + BTN[3]) / 2
    tw = d.textlength(btn_label, font=F_BTN)
    off = 34 if check else 0
    d.text((bx - tw / 2 + off, by - 38), btn_label, font=F_BTN,
           fill=(255, 255, 255, 255))
    if check:
        cx = bx - tw / 2 + off - 62
        d.line([(cx - 18, by), (cx, by + 20), (cx + 32, by - 24)],
               fill=(255, 255, 255, 255), width=12, joint="curve")
    tw = d.textlength(subtitle, font=F_SMALL)
    d.text(((W - tw) / 2, 356), subtitle, font=F_SMALL,
           fill=(140, 148, 163, 255))
    # credit, bottom-left
    d.text((32, H - 56), "Discord: hollow_misty", font=F_TINY,
           fill=(100, 108, 124, 255))
    return img


idle = panel((59, 130, 246, 255), "FIX INPUT", "resets foreground + stuck keys")
hover = panel((94, 155, 255, 255), "FIX INPUT", "resets foreground + stuck keys")
done = panel((40, 167, 90, 255), "DONE", "input reset sent", check=True)

# individual frames (previews / docs)
idle.save(os.path.join(HERE, "button.png"))
hover.save(os.path.join(HERE, "button_hover.png"))
done.save(os.path.join(HERE, "button_done.png"))

# raw RGBA dumps for the persistent GL texture, stored bottom-up (GL
# convention): the full idle panel as the base, plus per-state crops of the
# button band that get patched in with glTexSubImage2D
def gl_bytes(img):
    return img.transpose(Image.FLIP_TOP_BOTTOM).tobytes()


with open(os.path.join(HERE, "panel_base.rgba"), "wb") as f:
    f.write(gl_bytes(idle))
for name, frame in (("btn_idle.rgba", idle), ("btn_hover.rgba", hover),
                    ("btn_done.rgba", done)):
    with open(os.path.join(HERE, name), "wb") as f:
        f.write(gl_bytes(frame.crop(UPD_RECT)))

ic = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
di = ImageDraw.Draw(ic)
di.rounded_rectangle((8, 8, 248, 248), radius=24, fill=(22, 24, 29, 255),
                     outline=(59, 130, 246, 255), width=6)
cx, cy, rr = 128, 128, 68
di.arc((cx - rr, cy - rr, cx + rr, cy + rr), start=300, end=210,
       fill=(59, 130, 246, 255), width=18)
a = math.radians(300)
ax, ay = cx + rr * math.cos(a), cy + rr * math.sin(a)
di.polygon([(ax - 2, ay - 24), (ax + 26, ay - 5), (ax - 12, ay + 12)],
           fill=(59, 130, 246, 255))
ic.save(os.path.join(HERE, "icon.png"))
ic.save(os.path.join(HERE, "icon.ico"),
        sizes=[(16, 16), (32, 32), (48, 48), (256, 256)])
print("assets regenerated")
