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
    cards = [
        ("retail.png", "#18211b", "#d7ef41", "#e9ece6", "BOUTIQUE & RETAIL", "Festive Silk Edit", "20% offer · 15s reel"),
        ("florist.png", "#1c2017", "#f4b942", "#f6f2e6", "FLORIST & DECOR", "Fresh Jasmine", "Same-day garland drops"),
        ("food.png", "#211916", "#e88b5a", "#f5ebe2", "HOME KITCHEN", "Weekend Specials", "Order by WhatsApp"),
        ("beauty.png", "#161e20", "#5ad4c7", "#e8f4f2", "BEAUTY & CRAFT", "Botanical Glow", "Studio appointment reel"),
    ]
    for filename, bg, accent, ink, tag, title, sub in cards:
        im = Image.new("RGB", (600, 800), bg)
        d = ImageDraw.Draw(im)
        # Editorial dark frame + botanical/product geometric motif
        d.rounded_rectangle((34, 34, 566, 766), radius=24, outline=accent, width=3)
        d.ellipse((110, 175, 490, 555), fill="#101411", outline=accent, width=2)
        d.ellipse((165, 230, 435, 500), fill=accent)
        d.ellipse((205, 270, 395, 460), fill=bg)
        d.rounded_rectangle((245, 310, 355, 420), radius=18, fill=accent)
        d.text((300, 108), tag, font=font.font_variant(size=20), anchor="mm", fill=accent)
        d.text((300, 622), title, font=font.font_variant(size=36), anchor="mm", fill=ink)
        d.text((300, 676), sub, font=font.font_variant(size=22), anchor="mm", fill="#aeb9a4")
        im.save(destination / filename)


if __name__ == "__main__":
    generate()
    generate_lookbook()
