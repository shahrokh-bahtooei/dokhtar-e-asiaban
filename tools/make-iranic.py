"""Make «Sahel Iranic»: the Sahel font by Saber Rastikerdar, every outline slanted to the left.

Persian typography slants to the left (Iranic), not to the right like Latin italic. Sahel has no
slanted face, so browsers fake one by leaning the letters to the right. This script builds a real
left-leaning face from Sahel itself:

  * every glyph is decomposed and sheared: x' = x - tan(angle) * y  (tops move left);
  * mark anchors in GPOS (kasra, fatha, hamza, ...) get the same shear, so marks still sit right;
  * advance widths stay the same, so text set in it takes exactly the room of upright Sahel;
  * TrueType hinting is dropped (it no longer fits the new outlines);
  * names and style bits say «Sahel Iranic», Italic, with a positive (backslanted) italic angle.

Sahel is under the SIL Open Font License 1.1 with no Reserved Font Name; this Modified Version
stays under the same license (assets/fonts/OFL.txt).

usage: python3 make-iranic.py Sahel.ttf Sahel-Iranic.ttf Sahel-Iranic.woff2 [angle=12]
"""
import math
import sys

from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont

src, out_ttf, out_woff2 = sys.argv[1:4]
angle = float(sys.argv[4]) if len(sys.argv) > 4 else 12.0
k = math.tan(math.radians(angle))

font = TTFont(src)
glyph_set = font.getGlyphSet()
glyf, hmtx = font["glyf"], font["hmtx"]

# 1. shear every outline (composites decomposed first, so each point is moved exactly once)
sheared = {}
for name in font.getGlyphOrder():
    rec = DecomposingRecordingPen(glyph_set)
    glyph_set[name].draw(rec)
    pen = TTGlyphPen(None)
    rec.replay(TransformPen(pen, (1, 0, -k, 1, 0, 0)))
    sheared[name] = pen.glyph()
for name, g in sheared.items():
    glyf[name] = g
for name in font.getGlyphOrder():
    g = glyf[name]
    g.recalcBounds(glyf)
    adv, _ = hmtx[name]
    hmtx[name] = (adv, g.xMin if g.numberOfContours else 0)

# 2. shear the GPOS anchors the same way
def shear(anchor):
    if anchor is None:
        return
    anchor.XCoordinate = round(anchor.XCoordinate - k * anchor.YCoordinate)
    if anchor.Format != 1:            # anchor points and device tables belong to the old hinting
        anchor.Format = 1
        for attr in ("AnchorPoint", "XDeviceTable", "YDeviceTable"):
            if hasattr(anchor, attr):
                delattr(anchor, attr)

for lookup in font["GPOS"].table.LookupList.Lookup:
    for st in lookup.SubTable:
        kind = lookup.LookupType
        if kind == 9:
            kind, st = st.ExtensionLookupType, st.ExtSubTable
        if kind == 3:
            for r in st.EntryExitRecord:
                shear(r.EntryAnchor); shear(r.ExitAnchor)
        elif kind in (4, 5):
            for r in st.MarkArray.MarkRecord:
                shear(r.MarkAnchor)
            if kind == 4:
                for r in st.BaseArray.BaseRecord:
                    for a in r.BaseAnchor:
                        shear(a)
            else:
                for lig in st.LigatureArray.LigatureAttach:
                    for comp in lig.ComponentRecord:
                        for a in comp.LigatureAnchor:
                            shear(a)
        elif kind == 6:
            for r in st.Mark1Array.MarkRecord:
                shear(r.MarkAnchor)
            for r in st.Mark2Array.Mark2Record:
                for a in r.Mark2Anchor:
                    shear(a)

# 3. drop the hinting that fitted the upright outlines
for tag in ("fpgm", "prep", "cvt ", "hdmx", "LTSH", "VDMX"):
    if tag in font:
        del font[tag]
if "gasp" in font:
    font["gasp"].gaspRange = {0xFFFF: 0x000A}   # smooth at every size, no grid fitting
maxp = font["maxp"]
for attr in ("maxFunctionDefs", "maxInstructionDefs", "maxStackElements",
             "maxSizeOfInstructions", "maxTwilightPoints", "maxStorage"):
    setattr(maxp, attr, 0)
maxp.maxZones = 1

# 4. style bits and names
upm = font["head"].unitsPerEm
font["post"].italicAngle = angle                    # positive: leans to the left
font["hhea"].caretSlopeRise = upm
font["hhea"].caretSlopeRun = -round(k * upm)
font["head"].macStyle |= 0b10                        # italic
os2 = font["OS/2"]
os2.fsSelection = (os2.fsSelection | 0b1) & ~(1 << 6)  # ITALIC on, REGULAR off

names = {
    1: "Sahel Iranic",
    2: "Italic",
    3: "Sahel Iranic Italic",
    4: "Sahel Iranic Italic",
    6: "SahelIranic-Italic",
    10: f"Iranic (left-slanted) version of Sahel by Saber Rastikerdar: every outline slanted {angle:g}° to the left.",
    16: "Sahel Iranic",
    17: "Italic",
}
name_table = font["name"]
platforms = {(r.platformID, r.platEncID, r.langID) for r in name_table.names}
for nid, text in names.items():
    for plat in platforms:
        name_table.setName(text, nid, *plat)
for r in name_table.names:
    if r.nameID == 0:
        r.string = r.toUnicode() + f"\nSahel Iranic: a Modified Version of Sahel, every outline slanted {angle:g}° to the left."
    elif r.nameID == 5:
        r.string = r.toUnicode() + f"; Sahel Iranic, slanted {angle:g}°"

font.save(out_ttf)
font.flavor = "woff2"
font.save(out_woff2)
print("saved", out_ttf, out_woff2, f"angle {angle:g}")
