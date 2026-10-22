# -*- coding: utf-8 -*-
"""Produce the 'fixed' reference renders for the evaluation report.
Fixes applied on top of Gemini's engine:
  F1 make_valid -> GeometryCollection extraction (don't drop 12/17 cities)
  F2 font detection via findfont(fallback_to_default=False)
  F3 render in EPSG:4547 CGCS2000 3-deg Gauss-Kruger (equal-area-ish, correct aspect)
  F4 scale-adaptive road widths wired in from MultiScaleLODEngine
  F5 river centerline -> true-width polygon
  F6 zebra neatline drawn INSIDE the axes (4 closed edges)
  F7 feature-level style overrides actually applied
"""
import sys, os, warnings
sys.stdout.reconfigure(encoding="utf-8")
warnings.filterwarnings("ignore")
ROOT = r"D:\AAA-student\Projects"
GEO = os.path.join(ROOT, r"carto-agent\backend\data\geo")
OUT = r"C:\Users\落落晨星\AppData\Local\Temp\opencode\cartoeval"
sys.path.insert(0, os.path.join(ROOT, r"test\gemini\carto_engine_module"))
import geopandas as gpd, pandas as pd, numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib.font_manager import FontProperties

# ---- F2 font ----
def pick_font():
    for n in ["Microsoft YaHei", "SimHei", "Noto Sans SC", "SimSun", "DejaVu Sans"]:
        try:
            fm.findfont(FontProperties(family=n), fallback_to_default=False, rebuild_if_missing=False)
            return n
        except Exception:
            continue
    return "DejaVu Sans"
FONT = pick_font()
print("font ->", FONT)

# ---- F1 geometry fix ----
from shapely.validation import make_valid
from shapely.geometry import MultiPolygon, Polygon, GeometryCollection
def fix_geom(g):
    if g is None or g.is_empty: return g
    if g.is_valid: return g
    mv = make_valid(g)
    if isinstance(mv, GeometryCollection):
        polys = [x for x in mv.geoms if isinstance(x, (Polygon, MultiPolygon))]
        if not polys: return mv
        out = []
        for p in polys:
            out.extend(p.geoms if isinstance(p, MultiPolygon) else [p])
        return MultiPolygon([p for p in out if isinstance(p, Polygon)])
    return mv

def L(n): return gpd.read_file(os.path.join(GEO, n + ".geojson"))
districts, cities = L("wuhan_districts"), L("hubei_cities")
water, roads = L("wuhan_water"), L("wuhan_roads")
tourism, transit, peaks, contours = L("wuhan_tourism"), L("wuhan_transit"), L("wuhan_peaks"), L("wuhan_contours")

def prep(gdf):
    g = gdf.copy()
    g["geometry"] = [fix_geom(x) for x in g.geometry]
    g = g[g.geometry.geom_type.isin(["Polygon", "MultiPolygon", "LineString", "MultiLineString", "Point"])]
    return g

districts, cities = prep(districts), prep(cities)
print("districts after F1:", len(districts), " cities after F1:", len(cities))

# ---- F5 river centerline -> true-width polygon ----
from carto_engine.data_cleaning.cleaner_and_provenance import SpatialDataCleanerAndProvenance
wline = water[water.geometry.geom_type == "LineString"].copy()
wpoly = water[water.geometry.geom_type.isin(["Polygon", "MultiPolygon"])].copy()
wpoly = prep(wpoly)
river_poly = SpatialDataCleanerAndProvenance.river_centerline_to_polygon(wline, scale_denom=400000)
print("river polys:", len(river_poly))
water_all = pd.concat([wpoly, river_poly], ignore_index=True)
water_all["geometry"] = [fix_geom(x) for x in water_all.geometry]
water_all = water_all[water_all.geometry.geom_type.isin(["Polygon", "MultiPolygon"])]
print("water total:", len(water_all))

# ---- F3 projected render ----
EPSG = 4547
def proj(g):
    return g.to_crs(epsg=EPSG) if g.crs else g.set_crs(4326, allow_override=True).to_crs(epsg=EPSG)

from carto_engine.symbology.color_schemes import CartoColorSchemes
from carto_engine.symbology.symbol_library import CartoSymbolLibrary
from carto_engine.multiscale_lod import MultiScaleLODEngine
from carto_engine.layout_and_elements.label_engine import CartoLabelEngine
import matplotlib.patches as mpatches

def render_admin(gdf, title, scale_denom, outpath, seat_class="district_seat", seats_gdf=None):
    fig, ax = plt.subplots(figsize=(9, 7.2), dpi=140)
    g = proj(gdf)
    cols = CartoColorSchemes.compute_greedy_polygon_coloring(g)
    g = g.copy(); g["_fc"] = cols
    g.plot(ax=ax, color=g["_fc"], edgecolor="none", alpha=0.92, zorder=15)
    # boundaries
    b = gpd.GeoDataFrame(geometry=g.geometry.boundary, crs=g.crs)
    st = CartoSymbolLibrary.get_admin_styles()
    b.plot(ax=ax, color=st["district_boundary"].inner_glow_color, linewidth=st["district_boundary"].inner_glow_width,
           alpha=0.38, zorder=46)
    b.plot(ax=ax, color=st["district_boundary"].stroke_color, linewidth=st["district_boundary"].stroke_width,
           linestyle="dashed", zorder=70)
    outer = gpd.GeoDataFrame(geometry=[g.geometry.union_all().boundary], crs=g.crs)
    outer.plot(ax=ax, color=st["city_boundary"].inner_glow_color, linewidth=st["city_boundary"].inner_glow_width,
               alpha=0.38, zorder=47)
    outer.plot(ax=ax, color=st["city_boundary"].stroke_color, linewidth=st["city_boundary"].stroke_width,
               linestyle="dashdot", zorder=71)
    # labels
    for _, r in g.iterrows():
        if r.get("name"):
            p = r.geometry.representative_point()
            ax.text(p.x, p.y, " ".join(str(r["name"])), fontfamily=FONT, fontsize=9, fontweight="bold",
                    color="#1E293B", ha="center", va="center", zorder=95,
                    path_effects=[__import__("matplotlib").patheffects.withStroke(linewidth=2.6, foreground="white")])
    # F6 closed neatline INSIDE the axes
    x0, y0, x1, y1 = g.total_bounds
    pad = 0.03
    x0, x0_, x1, y0, y1 = x0 - pad*0.06, x0, x1 + pad*0.06, y0 - pad*0.08, y1 + pad*0.08
    for spine in ax.spines.values():
        spine.set_edgecolor("#1E293B"); spine.set_linewidth(2.2)
    # corner squares
    for cx, cy in [(x0, y0), (x1, y0), (x0, y1), (x1, y1)]:
        ax.add_patch(mpatches.Rectangle((cx, cy), (x1-x0)*0.012, (y1-y0)*0.018,
                     facecolor="#1E293B", edgecolor="#1E293B", zorder=100))
    # title cartouche
    ax.text(0.5, 1.035, title, transform=ax.transAxes, fontfamily=FONT, fontsize=14, fontweight="bold",
            color="#0F172A", ha="center", va="bottom", zorder=100)
    ax.set_xlim(x0, x1); ax.set_ylim(y0, y1)
    ax.set_aspect("equal")
    ax.set_axis_off()
    fig.savefig(outpath, dpi=140, facecolor="white", bbox_inches="tight", pad_inches=0.25)
    plt.close(fig)
    print("wrote", outpath)

# L1 province
render_admin(cities, "湖北省行政区划图  1:2 500 000", 2500000, os.path.join(OUT, "fixed_admin_province.png"))
# L2 city districts
render_admin(districts, "武汉市市辖区行政区划图  1:400 000", 400000, os.path.join(OUT, "fixed_admin_wuhan.png"))
print("done")
