"""
Konvertuje logo.png (tvoja slika) u logo.ico koji koristi
build_exe.bat da .exe fajl ima tvoju ikonu.

Kako koristiti:
1. Stavi svoju sliku loga u ovaj folder i nazovi je: logo.png
   (najbolje kvadratna slika, npr. 512x512 px, PNG sa providnom pozadinom)
2. Pokreni:  python convert_logo.py
3. Dobices logo.ico u istom folderu.
"""

import os
import sys

try:
    from PIL import Image
except ImportError:
    print("Nedostaje Pillow biblioteka. Instaliraj sa: pip install Pillow")
    sys.exit(1)

SRC = "logo.png"
DST = "logo.ico"

if not os.path.exists(SRC):
    print(f"Nisam pronasao '{SRC}' u ovom folderu.")
    print("Stavi svoju logo sliku ovdje i nazovi je tacno 'logo.png', pa pokreni ponovo.")
    sys.exit(1)

img = Image.open(SRC).convert("RGBA")
sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
img.save(DST, format="ICO", sizes=sizes)
print(f"Gotovo! Kreiran je '{DST}'.")
