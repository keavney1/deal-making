#!/bin/bash
# Render one Experiment 2 figure to a print-quality, transparent PNG.
#
#     scripts/exp2/render_figures.sh disclosure|credibility|reasoning
#
# Run make_dashboard_exp2.py --figure <name> first; this consumes the HTML it writes.
# Poster figures were produced with exactly this, so the outputs are reproducible.
#
# Three things here are load-bearing and easy to get wrong:
#   --default-background-color=00000000  transparent; without it Chrome composites onto white
#                                        and the figure shows as a pale plate on a tinted poster.
#   --force-device-scale-factor=12       ~560 dpi at 300mm wide. A1 posters are printed large.
#   alpha-bbox crop                      the window is deliberately oversized and the result is
#                                        cropped to the ink, so no figure carries dead margin.
#
# PNG only. Chrome can also --print-to-pdf a genuine vector version, but its fonts are not
# verifiably embedded and the page uses the macOS system font, so a print shop could substitute
# and reflow it. At this scale factor the raster is past any print requirement anyway.
set -e
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# The venv python, not whatever `python` happens to be on PATH — this needs PIL,
# and a bare `python` does not exist on a stock macOS shell.
PY="$REPO/.venv/bin/python"
[ -x "$PY" ] || PY="$(command -v python3)"
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
SF=12
NAME=$1
HTML="$REPO/results/exp2/figure_$NAME.html"
"$CHROME" --headless=new --disable-gpu --hide-scrollbars --default-background-color=00000000 \
  --force-device-scale-factor=$SF --window-size=660,520 --virtual-time-budget=5000 \
  --screenshot=/tmp/raw_$NAME.png "file://$HTML" 2>/dev/null
SF=$SF NAME=$NAME REPO="$REPO" "$PY" - <<'PY'
import os
from PIL import Image
sf, name = int(os.environ["SF"]), os.environ["NAME"]
im = Image.open(f"/tmp/raw_{name}.png").convert("RGBA")
l, t, r, b = im.getbbox()
pad = 6*sf
im2 = im.crop((max(l-pad,0), max(t-pad,0), min(r+pad,im.width), min(b+pad,im.height)))
out = f"{os.environ['REPO']}/results/exp2/figure_{name}.png"
im2.save(out, optimize=True)
w, h = im2.size
a = im2.getchannel("A").getcolors(256)
clear = sum(c for c, v in a if v == 0)
corners = [im2.convert("RGBA").getpixel(p)[3] for p in ((1,1),(w-2,1),(1,h-2),(w-2,h-2))]
print(f"  {name:12s} {w}x{h}px  css {(r-l)/sf:.0f}x{(b-t)/sf:.0f}  "
      f"{100*clear/(w*h):.0f}% transparent  corners_alpha={set(corners)}  "
      f"{w/(300/25.4):.0f} dpi at 300mm")
PY
rm -f /tmp/raw_$NAME.png
