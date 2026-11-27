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


if __name__ == "__main__":
    generate()
