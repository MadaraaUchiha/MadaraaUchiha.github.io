"""Vendor the map libraries and the world outline that life.html draws on.

The handed-off design pulled four things off two CDNs at run time: d3 7.9.0,
topojson-client 3.1.0, and the world-atlas country topology fetched from
jsdelivr inside the component's own boot. That is three third-party hosts on
the path to the first frame of the map, on a site that already went to the
trouble of serving its fonts itself.

Serving them from this origin removes all of it, and pins the versions in the
repository where they can be read rather than in a URL where they cannot.

Two changes from what the design asked for, both recorded here so a re-vendor
does not quietly undo them:

  * d3 7.9.0 in full is ~280 KB for four functions -- geoMercator, geoPath,
    geoGraticule and the projection's fitExtent. Only d3-geo is taken, with
    d3-array, which is the one package it needs. Same functions, a third of
    the bytes.
  * the country topology is committed rather than fetched, so the map draws
    on a cold cache and keeps drawing if jsdelivr does not answer.

    .venv\\Scripts\\python scripts\\fetch_map.py

Re-run only to change a version; the files are committed.
"""
from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "web" / "vendor"

# Pinned. d3-geo and topojson-client are the two libraries the map needs;
# d3-array is d3-geo's own dependency and its UMD build will not run without it.
ASSETS = {
    "d3-array.min.js":
        "https://cdn.jsdelivr.net/npm/d3-array@3.2.4/dist/d3-array.min.js",
    "d3-geo.min.js":
        "https://cdn.jsdelivr.net/npm/d3-geo@3.1.1/dist/d3-geo.min.js",
    "topojson-client.min.js":
        "https://cdn.jsdelivr.net/npm/topojson-client@3.1.0/dist/topojson-client.min.js",
    # Natural Earth 1:110m, quantised, as TopoJSON. The coastline the stations
    # sit on, and the only geometry the atlas lens needs.
    "world-110m.json":
        "https://cdn.jsdelivr.net/npm/world-atlas@2.0.2/countries-110m.json",
}

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, url in ASSETS.items():
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=60) as r:
            body = r.read()
        (OUT / name).write_bytes(body)
        print(f"  {len(body)/1024:7.1f} KB  {name}")

    total = sum(p.stat().st_size for p in OUT.iterdir() if p.is_file())
    print(f"vendored {len(ASSETS)} files, {total/1024:.0f} KB total, to {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
