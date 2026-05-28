from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw


SIZE = 1024
BG = "white"
OUT_DIR = Path("outputs/uploads")


def canvas() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", (SIZE, SIZE), BG)
    return image, ImageDraw.Draw(image)


def save(image: Image.Image, name: str) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / name
    image.save(path)
    print(path)


def agv() -> None:
    image, draw = canvas()
    draw.rounded_rectangle((220, 440, 804, 690), radius=36, fill="#607d8b", outline="#1f2937", width=10)
    draw.rounded_rectangle((350, 380, 670, 470), radius=28, fill="#90a4ae", outline="#1f2937", width=8)
    draw.rectangle((390, 330, 630, 380), fill="#b0bec5", outline="#1f2937", width=6)
    for x in (290, 430, 594, 734):
        draw.ellipse((x - 52, 640, x + 52, 744), fill="#111827", outline="#374151", width=6)
        draw.ellipse((x - 24, 668, x + 24, 716), fill="#9ca3af", outline="#374151", width=4)
    draw.ellipse((708, 500, 780, 572), fill="#111827", outline="#0f172a", width=4)
    draw.rectangle((220, 520, 260, 610), fill="#d97706")
    save(image, "reference-agv.png")


def robot_arm() -> None:
    image, draw = canvas()
    draw.ellipse((390, 760, 634, 920), fill="#d1d5db", outline="#4b5563", width=10)
    draw.ellipse((470, 700, 554, 784), fill="#f97316", outline="#7c2d12", width=8)
    draw.rounded_rectangle((486, 540, 540, 724), radius=24, fill="#fb923c", outline="#7c2d12", width=8)
    draw.ellipse((454, 500, 570, 612), fill="#f97316", outline="#7c2d12", width=8)
    draw.rounded_rectangle((396, 430, 520, 540), radius=22, fill="#fdba74", outline="#7c2d12", width=8)
    draw.ellipse((362, 388, 448, 474), fill="#f97316", outline="#7c2d12", width=8)
    draw.rounded_rectangle((300, 318, 394, 414), radius=18, fill="#fb923c", outline="#7c2d12", width=8)
    draw.line((292, 312, 248, 258), fill="#374151", width=14)
    draw.line((306, 324, 270, 270), fill="#374151", width=14)
    draw.line((238, 248, 214, 228), fill="#111827", width=10)
    draw.line((264, 262, 242, 220), fill="#111827", width=10)
    save(image, "reference-robot-arm.png")


def conveyor() -> None:
    image, draw = canvas()
    draw.polygon([(180, 610), (760, 610), (830, 520), (252, 520)], fill="#cbd5e1", outline="#475569")
    draw.polygon([(180, 610), (760, 610), (760, 662), (180, 662)], fill="#94a3b8", outline="#475569")
    for i in range(10):
        x0 = 222 + i * 54
        draw.ellipse((x0, 536, x0 + 40, 596), fill="#9ca3af", outline="#475569", width=4)
    for leg_x in (250, 410, 575, 732):
        draw.line((leg_x, 662, leg_x - 24, 846), fill="#475569", width=10)
        draw.line((leg_x + 34, 662, leg_x + 10, 846), fill="#475569", width=10)
        draw.line((leg_x - 54, 846, leg_x + 40, 846), fill="#64748b", width=8)
    draw.line((250, 508, 830, 508), fill="#1f2937", width=8)
    save(image, "reference-conveyor.png")


def rack() -> None:
    image, draw = canvas()
    for x in (240, 784):
        draw.rectangle((x, 170, x + 36, 830), fill="#2563eb", outline="#1e3a8a", width=6)
    for y in (250, 430, 610, 790):
        draw.rectangle((262, y, 784, y + 24), fill="#f97316", outline="#9a3412", width=5)
    box_colors = ["#d6a76c", "#c48a4d", "#b97a39"]
    for row, y in enumerate((282, 462, 642)):
        for col, x in enumerate((300, 470, 640)):
            draw.rectangle((x, y, x + 110, y + 90), fill=box_colors[(row + col) % 3], outline="#7c2d12", width=4)
            draw.line((x + 55, y, x + 55, y + 90), fill="#92400e", width=3)
    save(image, "reference-rack.png")


def safety_fence() -> None:
    image, draw = canvas()
    for x in (220, 420, 620, 820):
        draw.rectangle((x, 230, x + 22, 786), fill="#111827")
    panels = ((242, 420), (442, 620), (642, 820))
    for left, right in panels:
        draw.rectangle((left, 264, right, 744), fill="#facc15", outline="#111827", width=6)
        step = 34
        for offset in range(0, right - left, step):
            draw.line((left + offset, 264, left, 264 + offset), fill="#111827", width=2)
            draw.line((right - offset, 264, right, 264 + offset), fill="#111827", width=2)
            draw.line((left + offset, 744, right, 744 - offset), fill="#111827", width=2)
            draw.line((left, 744 - offset, left + offset, 744), fill="#111827", width=2)
    save(image, "reference-safety-fence.png")


if __name__ == "__main__":
    agv()
    robot_arm()
    conveyor()
    rack()
    safety_fence()
