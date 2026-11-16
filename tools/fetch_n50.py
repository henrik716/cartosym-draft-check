"""Fetch Kartverket N50 map data and place names for Rondane and store them as GeoJSON.

Usage: uv run --no-project --with pyogrio --with geopandas python tools/fetch_n50.py

Downloads N50 Kartdata (FGDB, EPSG:25833) for the seven municipalities around
Rondane from Geonorge, clips it to the same 45 x 30 km box as the elevation grid
(tools/fetch_rondane.py) and the Sentinel-2 scene, keeps a few layers with
English layer and property names, and writes them to
src/cartosym_draft/data/rondane/<Layer>.geojson in EPSG:25833. Place names come
from Kartverket's place name register (Sentral stedsnavnregister) API.

The downloads are cached in work/n50/ (git-ignored).

Map data and place names © Kartverket, CC BY 4.0.
"""

from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pyogrio
import shapely
from shapely.geometry import Point, box, mapping

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "work" / "n50"
OUT = ROOT / "src" / "cartosym_draft" / "data" / "rondane"

BBOX = (205000.0, 6860500.0, 250000.0, 6890500.0)  # the elevation grid's box, EPSG:25833
CLIP = box(*BBOX)
MUNICIPALITIES = ["3423_Stor-Elvdal", "3428_Alvdal", "3429_Folldal", "3431_Dovre", "3436_Nord-Fron", "3437_Sel",
                  "3439_Ringebu"]
DOWNLOAD = "https://nedlasting.geonorge.no/geonorge/Basisdata/N50Kartdata/FGDB/Basisdata_{}_25833_N50Kartdata_FGDB.zip"
PLACES_API = "https://api.kartverket.no/stedsnavn/v1/punkt"
ATTRIBUTION = "Map data © Kartverket, CC BY 4.0"
PRECISION = 0.1  # metres: at 1:4 000 a whole metre is about one screen pixel, which put kinks in curves

LANDCOVER = {"Innsjø": "lake", "Elv": "river", "Myr": "bog", "Skog": "forest", "ÅpentOmråde": "open",
             "DyrketMark": "farmland", "Tettbebyggelse": "urban", "Steinbrudd": "quarry", "Steintipp": "quarry",
             "Industriområde": "industrial", "SportIdrettPlass": "sports", "Gravplass": "cemetery",
             "Alpinbakke": "skiSlope", "FerskvannTørrfall": "dryRiverbed"}
ROAD_CATEGORY = {"E": "european", "R": "national", "F": "county", "K": "municipal", "P": "private"}
ROAD_TYPE = {"traktorveg": "tractor", "sti": "path", "gangOgSykkelveg": "cycleway"}
HUT_SERVICE = {"Betjent": "staffed", "Ubetjent": "selfService", "Rastebu": "shelter"}
PROTECTION = {"NP": "nationalPark", "NR": "natureReserve", "LVO": "landscapeProtection"}
PLACE_TYPE = {"Fjell": "mountain", "Topp": "peak", "Vann": "lake", "Innsjø": "lake", "Tjern": "pond", "Dal": "valley",
              "Elv": "river", "Turisthytte": "hut", "Seter": "summerFarm", "Bygdelag (bygd)": "village",
              "Tettsted": "village", "Grend": "hamlet"}


def download() -> list[Path]:
    CACHE.mkdir(parents=True, exist_ok=True)
    gdbs = []
    for m in MUNICIPALITIES:
        z = CACHE / f"{m}.zip"
        if not z.exists():
            print("downloading", m, file=sys.stderr)
            urllib.request.urlretrieve(DOWNLOAD.format(m), z)
        d = CACHE / m
        if not d.exists():
            with zipfile.ZipFile(z) as zf:
                zf.extractall(d)
        gdbs.extend(d.glob("*.gdb"))
    return gdbs


def read(gdbs: list[Path], name: str) -> gpd.GeoDataFrame:
    layer = next(n for n, _ in pyogrio.list_layers(gdbs[0]) if n == name)
    parts = [pyogrio.read_dataframe(g, layer=layer, bbox=BBOX) for g in gdbs]
    df = pd.concat([p for p in parts if len(p)], ignore_index=True)
    return gpd.GeoDataFrame(df, geometry="geometry", crs="EPSG:25833")


def clip(df: gpd.GeoDataFrame, tolerance: float) -> gpd.GeoDataFrame:
    df = df.copy()
    df["geometry"] = df.geometry.intersection(CLIP).simplify(tolerance, preserve_topology=True)
    df = df[~df.geometry.is_empty & df.geometry.notna()]
    return df


def dedupe(df: gpd.GeoDataFrame, keys: list[str]) -> gpd.GeoDataFrame:
    """The same feature can come from two neighbouring municipalities' files."""
    wkb = df.geometry.apply(lambda g: shapely.to_wkb(shapely.set_precision(g, 1.0)))
    return df[~pd.DataFrame({**{k: df[k].astype(str) for k in keys}, "_g": wkb}).duplicated()]


def _round(coords):
    if isinstance(coords, (int, float)):
        return round(coords, 1)
    if coords and isinstance(coords[0], (int, float)):
        return [round(c, 1) for c in coords]
    return [_round(c) for c in coords]


def _single(geom):
    """Plain Polygon or LineString when a Multi* has one part, which most readers prefer."""
    if geom.geom_type.startswith("Multi") and len(geom.geoms) == 1:
        return geom.geoms[0]
    return geom


def write(name: str, rows: list[tuple[dict, object]], description: str) -> None:
    feats = []
    for props, geom in rows:
        geom = shapely.set_precision(geom, PRECISION)  # keeping polygons valid
        if geom.is_empty:
            continue
        g = mapping(_single(geom))
        g = {"type": g["type"], "coordinates": _round(json.loads(json.dumps(g["coordinates"])))}
        feats.append({"type": "Feature", "properties": {k: v for k, v in props.items() if v is not None}, "geometry": g})
    fc = {"type": "FeatureCollection", "name": name, "description": description, "attribution": ATTRIBUTION,
          "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::25833"}}, "features": feats}
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{name}.geojson"
    path.write_text(json.dumps(fc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{name}: {len(feats)} features, {path.stat().st_size // 1024} KiB", file=sys.stderr)


def merge_lines(rows: list[tuple[dict, object]]) -> list[tuple[dict, object]]:
    """Join line pieces that meet end to end and have exactly the same properties.

    N50 starts a new feature wherever any attribute changes and at municipal borders, so one road is often
    several features. Strokes have butt caps (clause 8), which leave a notch where two pieces meet at a bend.
    Only pieces whose properties are all equal (validDate included) are joined, so no information is lost;
    pieces still meet at junctions, where three or more lines end at one point.
    """
    from shapely.ops import linemerge
    groups: dict[str, tuple[dict, list]] = {}
    for props, geom in rows:
        key = json.dumps(props, sort_keys=True)
        parts = getattr(geom, "geoms", [geom])
        groups.setdefault(key, (props, []))[1].extend(shapely.set_precision(g, PRECISION) for g in parts)
    out = []
    for props, parts in groups.values():
        merged = linemerge([g for g in parts if not g.is_empty])
        out += [(dict(props), line) for line in getattr(merged, "geoms", [merged])]
    print(f"  joined {len(rows)} line features into {len(out)}", file=sys.stderr)
    return out


def _str(v):
    return None if v is None or (isinstance(v, float) and pd.isna(v)) or v == "" else str(v)


def _date(r):
    """validDate: the update date, or the capture date where the update date is N50's 1000-01-01 placeholder."""
    for v in (getattr(r, "oppdateringsdato", None), getattr(r, "datafangstdato", None)):
        if v is not None and not pd.isna(v) and v.year > 1000:
            return v.strftime("%Y-%m-%d")
    return None


def _int(v):
    return None if v is None or pd.isna(v) else int(round(float(v)))


def landcover(gdbs):
    df = read(gdbs, "N50_Arealdekke_omrade")
    df = df[df.objtype.isin(LANDCOVER)].copy()
    df["geometry"] = df.geometry.intersection(CLIP)
    df["class"] = df.objtype.map(LANDCOVER)
    rows = []
    # Each municipality's file is cut at its border: merge touching pieces of the same class, so a lake
    # across a border is one feature without a seam in its outline. Name and elevation come from the
    # largest named piece.
    for cls, part in df.groupby("class"):
        merged = shapely.unary_union(part.geometry.buffer(0.01).values).buffer(-0.01)
        sidx = part.sindex
        for poly in getattr(merged, "geoms", [merged]):
            hits = part.iloc[sidx.query(poly, predicate="intersects")]
            if not len(hits) or poly.area < 1:
                continue  # a sliver left by the buffer used for merging
            named = hits[hits.navn.notna()]
            best = named.iloc[named.geometry.intersection(poly).area.argmax()] if len(named) else None
            largest = hits.iloc[hits.geometry.intersection(poly).area.argmax()]
            props = {"class": cls, "name": _str(best.navn) if best is not None else None,
                     "elevation": _int(best.hoyde) if best is not None and cls == "lake" else None,
                     "area": _int(poly.area), "validDate": _date(largest)}
            rows.append((props, poly.simplify(5, preserve_topology=True)))
    rows.sort(key=lambda p: -p[0]["area"])  # large areas first, so small ones are drawn on top
    write("Landcover", rows, "N50 land cover: class is lake, river, bog, forest, open, farmland, urban, quarry, "
          "industrial, sports, cemetery, skiSlope or dryRiverbed; lakes have elevation (m); area in m²; validDate is "
          "N50's update date (or capture date where that is unknown)")


def rivers(gdbs):
    df = clip(read(gdbs, "N50_Arealdekke_senterlinje"), 5)
    df = dedupe(df[df.objtype.isin(["ElvBekk", "ElvMidtlinje"])], ["objtype"])
    rows = merge_lines([({"class": "stream" if r.objtype == "ElvBekk" else "river"}, r.geometry)
                        for r in df.itertuples()])
    write("Rivers", rows, "N50 rivers and streams as lines: class is stream (narrow) or river (the centre line of a "
          "river also mapped as a Landcover area)")


def roads(gdbs):
    df = clip(read(gdbs, "N50_Samferdsel_senterlinje"), 3)
    df = dedupe(df[df.objtype == "Veglenke"], ["typeveg", "vegkategori"])
    order = ["european", "national", "county", "municipal", "private", "cycleway", "tractor", "path"]
    rows = []
    for r in df.itertuples():
        cls = ROAD_CATEGORY.get(_str(r.vegkategori)) if r.typeveg in ("enkelBilveg", "kanalisertVeg") else ROAD_TYPE.get(r.typeveg)
        if cls is None:
            continue
        props = {"class": cls, "number": _int(r.vegnummer) if cls in ("european", "national", "county") else None,
                 "validDate": _date(r)}
        if cls == "path":
            props["marked"] = r.rutemerking == "JA"
        rows.append((props, r.geometry))
    rows = merge_lines(rows)
    rows.sort(key=lambda p: -order.index(p[0]["class"]))  # paths first, European roads last
    write("Roads", rows, "N50 roads and paths: class is european, national, county, municipal, private, cycleway, "
          "tractor or path; number for european, national and county roads; marked (boolean) for paths with a "
          "marked hiking route; validDate is N50's update date (or capture date where that is unknown)")


def railways(gdbs):
    df = dedupe(clip(read(gdbs, "N50_Samferdsel_senterlinje"), 3).query("objtype == 'Bane'"), ["objtype"])
    write("Railways", [({}, r.geometry) for r in df.itertuples()], "N50 railway lines")


def huts(gdbs):
    df = clip(read(gdbs, "N50_BygningerOgAnlegg_posisjon"), 0)
    df = df[df.navn.notna() & df.betjeningsgrad.isin(HUT_SERVICE)]
    df = df.drop_duplicates("navn")
    rows = [({"name": r.navn, "service": HUT_SERVICE[r.betjeningsgrad], "validDate": _date(r)}, r.geometry)
            for r in df.itertuples()]
    write("Huts", rows, "N50 tourist cabins: service is staffed, selfService or shelter; validDate is N50's update "
          "date (or capture date where that is unknown)")


def buildings(gdbs):
    df = clip(read(gdbs, "N50_BygningerOgAnlegg_posisjon"), 0)
    df = dedupe(df[(df.objtype == "Bygning") & df.navn.isna()], ["objtype"])
    write("Buildings", [({"type": _int(r.bygningstype)}, r.geometry) for r in df.itertuples()],
          "N50 buildings as points: type is the building type code from the Norwegian cadastre (for example "
          "111 detached house, 161 cabin, 241 farm building)")


def contours(gdbs):
    df = clip(read(gdbs, "N50_Høyde_senterlinje"), 10)
    df = dedupe(df[df.objtype == "Høydekurve"], ["hoyde"])
    write("Contours", [({"elevation": _int(r.hoyde)}, r.geometry) for r in df.itertuples()],
          "N50 contour lines every 20 m: elevation in metres")


def spot_heights(gdbs):
    df = dedupe(clip(read(gdbs, "N50_Høyde_posisjon"), 0), ["hoyde"])
    rows = [({"elevation": _int(r.hoyde), "trig": r.objtype == "TrigonometriskPunkt"}, r.geometry)
            for r in df.itertuples()]
    write("SpotHeights", rows, "N50 spot heights: elevation in metres; trig is true for trigonometric points")


def protected_areas(gdbs):
    df = clip(read(gdbs, "N50_Restriksjonsområder_omrade"), 10)
    df = df[(df.objtype == "Naturvernområde") & df.verneform.isin(PROTECTION)]
    df = df.dissolve(by=["navn", "verneform"], as_index=False)
    rows = [({"name": r.navn, "class": PROTECTION[r.verneform]}, r.geometry) for r in df.itertuples()]
    write("ProtectedAreas", rows, "N50 protected areas, one feature per area: class is nationalPark, "
          "natureReserve or landscapeProtection")


def municipalities(gdbs):
    df = clip(read(gdbs, "N50_AdministrativeOmråder_omrade"), 10).dissolve(by=["kommunenavn", "kommunenummer"],
                                                                           as_index=False)
    rows = [({"name": r.kommunenavn, "number": _int(r.kommunenummer)}, r.geometry) for r in df.itertuples()]
    write("Municipalities", rows, "N50 municipalities, clipped to the box: name and number")


def places(spot: gpd.GeoDataFrame) -> None:
    """Place names from the register, queried on a grid of 5 km circles that covers the box."""
    seen, rows = set(), []
    for y in range(int(BBOX[1]) + 2500, int(BBOX[3]), 3500):
        for x in range(int(BBOX[0]) + 2500, int(BBOX[2]), 3500):
            page = 1
            while True:
                q = urllib.parse.urlencode({"nord": y, "ost": x, "koordsys": 25833, "radius": 2500, "utkoordsys": 25833,
                                            "treffPerSide": 500, "side": page})
                with urllib.request.urlopen(f"{PLACES_API}?{q}", timeout=60) as resp:
                    d = json.load(resp)
                for s in d["navn"]:
                    t = PLACE_TYPE.get(s["navneobjekttype"])
                    if t is None or s["stedsnummer"] in seen:
                        continue
                    seen.add(s["stedsnummer"])
                    p = s["representasjonspunkt"]
                    pt = Point(p["øst"], p["nord"])
                    if not CLIP.contains(pt):
                        continue
                    names = [n for n in s["stedsnavn"] if n.get("navnestatus") == "hovednavn"] or s["stedsnavn"]
                    name = next((n["skrivemåte"] for n in names if "prioritert" in n.get("skrivemåtestatus", "")),
                                names[0]["skrivemåte"])
                    rows.append(({"name": name, "type": t}, pt))
                if d["metadata"]["viserTil"] >= d["metadata"]["totaltAntallTreff"]:
                    break
                page += 1
    # Peaks and mountains: the elevation of the nearest spot height within 300 m, if any.
    sidx = spot.sindex
    for props, pt in rows:
        if props["type"] in ("mountain", "peak"):
            i = sidx.nearest(pt, max_distance=300, return_all=False)
            if len(i[1]):
                props["elevation"] = _int(spot.iloc[int(i[1][0])].hoyde)
    rows.sort(key=lambda r: (r[0]["type"], r[0]["name"]))
    write("Places", rows, "Place names from Kartverket's place name register: type is mountain, peak, lake, pond, "
          "valley, river, hut, summerFarm, village or hamlet; mountains and peaks have the elevation (m) of the "
          "nearest N50 spot height within 300 m, where there is one")


def name_lakes() -> None:
    """N50 lake areas rarely carry a name: take it from a lake or pond place name inside the lake."""
    from shapely.geometry import shape
    from shapely.strtree import STRtree
    path = OUT / "Landcover.geojson"
    fc = json.loads(path.read_text(encoding="utf-8"))
    pts = [f for f in json.loads((OUT / "Places.geojson").read_text(encoding="utf-8"))["features"]
           if f["properties"]["type"] in ("lake", "pond")]
    tree = STRtree([shape(p["geometry"]) for p in pts])
    named = 0
    for f in fc["features"]:
        p = f["properties"]
        if p["class"] != "lake" or "name" in p:
            continue
        hit = tree.query(shape(f["geometry"]), predicate="contains")
        if len(hit):
            p["name"] = pts[int(hit[0])]["properties"]["name"]
            named += 1
    path.write_text(json.dumps(fc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Landcover: named {named} lakes from place names", file=sys.stderr)


def main() -> int:
    gdbs = download()
    landcover(gdbs)
    rivers(gdbs)
    roads(gdbs)
    railways(gdbs)
    huts(gdbs)
    buildings(gdbs)
    contours(gdbs)
    spot_heights(gdbs)
    protected_areas(gdbs)
    municipalities(gdbs)
    places(dedupe(clip(read(gdbs, "N50_Høyde_posisjon"), 0), ["hoyde"]))
    name_lakes()
    return 0


if __name__ == "__main__":
    sys.exit(main())
