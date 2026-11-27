"""Original illustrated bakery cards and a synthetic chord bed; no downloaded media."""
import math
import struct
import wave
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]


def generate(destination: Path = ROOT / "assets/demo"):
    destination.mkdir(parents=True, exist_ok=True)
    font = ImageFont.truetype(str(ROOT / "assets/fonts/NotoSansTamil.ttf"), 48)
    palettes = [("#f5c8bb", "#6b3629", "Chocolate cake"), ("#c7dace", "#945638", "Fresh brownies"), ("#ded0e8", "#a54b60", "Berry cupcakes"), ("#f1dda8", "#c27a3a", "Butter cookies")]
    for index, (background, icing, label) in enumerate(palettes):
        image = Image.new("RGB", (900, 1200), background)
        d = ImageDraw.Draw(image)
        d.ellipse((110, 530, 790, 970), fill="#ffffff")
        if index == 0:
            d.rounded_rectangle((210, 440, 690, 780), 35, fill=icing)
            d.ellipse((210, 355, 690, 550), fill="#4b2826")
            for x in range(260, 660, 80):
                d.ellipse((x, 385, x+35, 420), fill="#f5c8bb")
        else:
            for x, y in [(210, 480), (460, 480), (210, 690), (460, 690)]:
                d.rounded_rectangle((x, y, x+190, y+160), 50 if index == 3 else 20, fill=icing)
                d.ellipse((x+35, y+20, x+150, y+90), fill="#f5e6d4")
        d.text((450, 145), "THE LITTLE BAKERY", font=font.font_variant(size=30), anchor="mm", fill="#352c32")
        d.text((450, 260), label, font=font, anchor="mm", fill="#352c32")
        d.text((450, 1060), "Baked with love. Shared with joy.", font=font.font_variant(size=27), anchor="mm", fill="#352c32")
        image.save(destination / f"bakery-{index+1}.png")
    rate, duration = 22050, 8
    with wave.open(str(destination / "music.wav"), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(rate)
        frames = bytearray()
        for sample in range(rate * duration):
            t = sample / rate
            chord = [(261.63, 329.63, 392), (220, 261.63, 329.63), (174.61, 220, 261.63), (196, 246.94, 293.66)][int(t // 2) % 4]
            envelope = min(1, (t % 2)*5) * min(1, (2-t % 2)*5)
            value = sum(math.sin(2*math.pi*f*t) for f in chord)/3
            frames.extend(struct.pack("<h", int(value*envelope*10000)))
        audio.writeframes(frames)


def generate_lookbook(destination: Path = ROOT / "frontend/public/lookbook"):
    destination.mkdir(parents=True, exist_ok=True)
    font = ImageFont.truetype(str(ROOT / "assets/fonts/NotoSansTamil.ttf"), 34)

    def frame(bg: str, accent: str):
        im = Image.new("RGB", (600, 800), bg)
        d = ImageDraw.Draw(im)
        d.rounded_rectangle((30, 30, 570, 770), radius=24, outline=accent, width=3)
        d.rounded_rectangle((46, 46, 554, 754), radius=18, outline="#2c332d", width=1)
        return im, d

    def label_block(d: ImageDraw.ImageDraw, accent: str, ink: str, tag: str, title: str, sub: str):
        d.rounded_rectangle((66, 78, 330, 114), radius=18, fill="#0c0f0d")
        d.text((198, 96), tag, font=font.font_variant(size=16), anchor="mm", fill=accent)
        d.rounded_rectangle((396, 78, 534, 114), radius=18, fill=accent)
        d.text((465, 96), "9:16 REEL", font=font.font_variant(size=15), anchor="mm", fill="#111509")
        d.rounded_rectangle((60, 574, 540, 728), radius=18, fill="#0c0f0d")
        d.text((300, 622), title, font=font.font_variant(size=35), anchor="mm", fill=ink)
        d.text((300, 676), sub, font=font.font_variant(size=20), anchor="mm", fill="#aeb9a4")

    # 1. Boutique & Retail — layered silk drape & woven diamond zari motif
    im, d = frame("#141c17", "#d7ef41")
    for pts, col in [
        ([(90, 545), (210, 175), (355, 175), (245, 545)], "#233627"),
        ([(195, 545), (305, 170), (485, 170), (395, 545)], "#2e462f"),
        ([(325, 545), (425, 200), (520, 200), (480, 545)], "#425f28"),
    ]:
        d.polygon(pts, fill=col)
    for y in range(215, 515, 52):
        d.polygon([(310, y - 13), (326, y), (310, y + 13), (294, y)], fill="#d7ef41")
    d.line([(160, 510), (470, 205)], fill="#d7ef41", width=6)
    d.line([(184, 526), (494, 221)], fill="#ecf99c", width=2)
    label_block(d, "#d7ef41", "#eef3ea", "BOUTIQUE & RETAIL", "Festive Silk Edit", "20% offer · 15s reel")
    im.save(destination / "retail.png")

    # 2. Florist & Decor — blooming garland medallion & jasmine petals
    im, d = frame("#161d14", "#f4b942")
    d.ellipse((125, 175, 475, 525), fill="#1c2718", outline="#6ea36a", width=3)
    cx, cy, rad = 300, 350, 128
    for step in range(12):
        ang = step * (2 * math.pi / 12)
        px = cx + math.cos(ang) * rad
        py = cy + math.sin(ang) * rad
        color = "#f4b942" if step % 2 == 0 else "#f6f1de"
        d.ellipse((px - 34, py - 34, px + 34, py + 34), fill=color)
        d.ellipse((px - 12, py - 12, px + 12, py + 12), fill="#c77920" if step % 2 == 0 else "#6ea36a")
    d.ellipse((245, 295, 355, 405), fill="#6ea36a")
    d.ellipse((267, 317, 333, 383), fill="#f4b942")
    label_block(d, "#f4b942", "#f6f2e6", "FLORIST & DECOR", "Fresh Jasmine", "Same-day garland drops")
    im.save(destination / "florist.png")

    # 3. Home Kitchen — brass thali & banana leaf platter with warm garnish
    im, d = frame("#211714", "#e88b5a")
    d.rounded_rectangle((110, 205, 490, 520), radius=145, fill="#283d25", outline="#6ea36a", width=3)
    d.ellipse((150, 222, 450, 502), fill="#38241d", outline="#e88b5a", width=5)
    d.ellipse((188, 258, 412, 466), fill="#d96b38")
    for ox, oy, col in [
        (252, 330, "#f5cb86"),
        (322, 318, "#d7ef41"),
        (288, 388, "#f7e6cf"),
        (345, 380, "#f5cb86"),
        (248, 392, "#6ea36a"),
    ]:
        d.ellipse((ox - 16, oy - 16, ox + 16, oy + 16), fill=col)
    for ox, oy, r in [(245, 165, 8), (300, 150, 10), (355, 165, 8), (272, 185, 6), (328, 185, 6)]:
        d.ellipse((ox - r, oy - r, ox + r, oy + r), fill="#f4cdb4")
    label_block(d, "#e88b5a", "#f5ebe2", "HOME KITCHEN", "Weekend Specials", "Order by WhatsApp")
    im.save(destination / "food.png")

    # 4. Beauty & Craft — botanical elixir bottle & leaf silhouette
    im, d = frame("#131c1e", "#5ad4c7")
    d.ellipse((135, 180, 465, 510), fill="#182729", outline="#5ad4c7", width=2)
    d.polygon([(195, 470), (145, 320), (240, 385)], fill="#2b524d")
    d.polygon([(405, 470), (455, 320), (360, 385)], fill="#2b524d")
    d.rounded_rectangle((242, 278, 358, 486), radius=26, fill="#5ad4c7")
    d.rounded_rectangle((258, 298, 274, 466), radius=8, fill="#ccf7f2")
    d.rounded_rectangle((274, 234, 326, 284), radius=10, fill="#1c2729", outline="#d7ef41", width=2)
    d.rounded_rectangle((287, 198, 313, 240), radius=8, fill="#d7ef41")
    d.rounded_rectangle((256, 350, 344, 422), radius=10, fill="#111819")
    d.text((300, 386), "GLOW", font=font.font_variant(size=20), anchor="mm", fill="#5ad4c7")
    label_block(d, "#5ad4c7", "#e8f4f2", "BEAUTY & CRAFT", "Botanical Glow", "Studio appointment reel")
    im.save(destination / "beauty.png")


if __name__ == "__main__":
    generate()
    generate_lookbook()
