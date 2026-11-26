"""Debug helper: puts several rendered cases side by side (for looking at them)."""
import os
import sys
from PIL import Image, ImageDraw

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
cases = sys.argv[2:]
scale = 2
ims = [Image.open(os.path.join(ROOT, 'out', '%s-1.png' % c)) for c in cases]
cols = 2
w = max(i.width for i in ims) * scale
h = max(i.height for i in ims) * scale + 16
rows = (len(ims) + cols - 1) // cols
sheet = Image.new('RGB', (cols * w + (cols - 1) * 8, rows * h), (128, 128, 128))
d = ImageDraw.Draw(sheet)
for k, (c, im) in enumerate(zip(cases, ims)):
    x = (k % cols) * (w + 8)
    y = (k // cols) * h
    sheet.paste(im.resize((im.width * scale, im.height * scale), Image.NEAREST), (x, y + 16))
    d.text((x + 2, y + 2), c, fill=(255, 255, 255))
os.makedirs(os.path.join(ROOT, 'renderer', 'debug'), exist_ok=True)
sheet.save(os.path.join(ROOT, 'renderer', 'debug', sys.argv[1]))
