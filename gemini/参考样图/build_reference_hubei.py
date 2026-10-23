# -*- coding: utf-8 -*-
"""FINAL REFERENCE BUILD — 湖北省行政区划图 with province-wide hydrography + DEM.
Pipeline mirrors what the carto module must implement:
  ACQUIRE -> CLEAN -> PROJECT -> TERRAIN -> GENERALIZE -> SYMBOLIZE -> ANNOTATE -> COMPOSE
"""
import sys, os, glob, zipfile
sys.stdout.reconfigure(encoding="utf-8")
import numpy as np, geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.font_manager as fm
import matplotlib.patheffects as pe
from matplotlib.font_manager import FontProperties
from matplotlib.colors import LinearSegmentedColormap, LightSource
from shapely.geometry import MultiPolygon, Polygon, GeometryCollection
from shapely.validation import make_valid
from scipy.interpolate import RegularGridInterpolator

GEO = r"C:\Users\落落晨星\AppData\Local\Temp\opencode\geo"
REPO = r"D:\AAA-student\Projects\carto-agent\backend\data\geo"
EPSG = 4547

def pick_font():
    for n in ["Microsoft YaHei", "SimHei", "Noto Sans SC", "SimSun", "DejaVu Sans"]:
        try:
            fm.findfont(FontProperties(family=n), fallback_to_default=False, rebuild_if_missing=False)
            return n
        except Exception: continue
    return "DejaVu Sans"
FONT = pick_font()
SANS = "DejaVu Sans"
print("font:", FONT)

# ---------- ACQUIRE ----------
z = zipfile.ZipFile(os.path.join(GEO, "gadm41_CHN_2.json.zip"))
with z.open(z.namelist()[0]) as f: gadm = gpd.read_file(f)
CN = {"EnshiTujiaandMiao":"恩施","Ezhou":"鄂州","Huanggang":"黄冈","Huangshi":"黄石",
      "Jingmen":"荆门","Jingzhou":"荆州","Qianjiang":"潜江","Shennongjia":"神农架",
      "Shiyan":"十堰","SuizhouShi":"随州","Tianmen":"天门","Wuhan":"武汉","Xiangfan":"襄阳",
      "Xianning":"咸宁","Xiantao":"仙桃","Xiaogan":"孝感","Yichang":"宜昌"}
hb = gadm[gadm["NAME_1"]=="Hubei"].copy().reset_index(drop=True)
hb["name_cn"] = hb["NAME_2"].map(CN)
hb = hb[["name_cn","geometry"]]
riv = gpd.read_file(os.path.join(GEO, "osm_hubei_rivers.geojson"))
print(f"acquired: {len(hb)} prefectures, {len(riv)} river lines")

# ---------- CLEAN ----------
def clean(gdf):
    out = gdf.copy(); gs = []
    for g in out.geometry:
        if g is None or g.is_empty: gs.append(g); continue
        if not g.is_valid:
            mv = make_valid(g)
            if isinstance(mv, GeometryCollection):
                ps=[p for p in mv.geoms if isinstance(p,(Polygon,MultiPolygon))]
                parts=[q for p in ps for q in (p.geoms if hasattr(p,'geoms') else [p])]
                parts=[q for q in parts if q.geom_type=="Polygon" and q.area>0]
                mv = MultiPolygon(parts) if parts else None
            g = mv
        gs.append(g)
    out["geometry"]=gs
    return out[out.geometry.geom_type.isin(["Polygon","MultiPolygon"])].copy()
hb = clean(hb)
riv = riv[riv.geometry.notnull() & ~riv.geometry.is_empty]
print(f"cleaned: admin {len(hb)} (invalid {(~hb.geometry.is_valid).sum()}), rivers {len(riv)}")

# ---------- PROJECT ----------
hbp = hb.to_crs(epsg=EPSG); rivp = riv.to_crs(epsg=EPSG)

# ---------- TERRAIN ----------
print("terrain: reading SRTM …")
def read_hgt(p):
    a = np.fromfile(p, dtype=">i2")
    n = int(round((a.size) ** 0.5))
    return a.reshape(n, n).astype("float32")
SUB = 4   # downsample 1-arcsec DEM (~30 m) -> ~120 m, plenty for 1:2.5M
tiles={}
for f in sorted(glob.glob(os.path.join(GEO,"dem","*.hgt"))):
    b=os.path.basename(f); lat=int(b[1:3]); lon=int(b[4:7])
    tiles[(lat,lon)] = read_hgt(f)[::SUB, ::SUB]
print(f"  {len(tiles)} tiles (subsampled x{SUB})")
lats=sorted({k[0] for k in tiles}); lons=sorted({k[1] for k in tiles})
NS=next(iter(tiles.values())).shape[0]
def longest_run(vals):
    best=[]; cur=[]
    for v in sorted(vals):
        if cur and v == cur[-1]+1: cur.append(v)
        else:
            if len(cur) > len(best): best = cur
            cur=[v]
    if len(cur) > len(best): best = cur
    return best
lons_run = longest_run(lons); lats_run = longest_run(lats)
print(f"  contiguous block: lat {lats_run} x lon {lons_run}")
lats = lats_run; lons = lons_run
# seamless mosaic: build the FULL tile grid, then crop to a contiguous window
FULL_LAT = range(29, 34)
FULL_LON = range(108, 117)
grid = np.full((len(FULL_LAT)*NS, len(FULL_LON)*NS), np.nan, dtype="float32")
for i,la in enumerate(FULL_LAT):
    for j,lo in enumerate(FULL_LON):
        if (la,lo) in tiles:
            grid[i*NS:(i+1)*NS, j*NS:(j+1)*NS] = tiles[(la,lo)]
# fill NaN gaps by nearest-valid column/row propagation (removes tile seams)
for i in range(grid.shape[0]):
    row = grid[i]
    if np.all(np.isnan(row)): continue
    idx = np.where(~np.isnan(row))[0]
    grid[i] = np.interp(np.arange(len(row)), idx, row[idx])
# fill whole missing rows (lat bands entirely missing) by vertical interpolation
for j in range(grid.shape[1]):
    col = grid[:, j]
    if np.all(np.isnan(col)): continue
    idx = np.where(~np.isnan(col))[0]
    if len(idx) < len(col):
        grid[:, j] = np.interp(np.arange(len(col)), idx, col[idx])
step = 1.0/NS
xs_full = [lo + np.arange(NS)*step for lo in FULL_LON]
X = np.concatenate(xs_full)
ys_full = [la + 1.0 - np.arange(NS)*step for la in sorted(FULL_LAT, reverse=True)]
Y = np.concatenate(ys_full)
Z = grid
print(f"  mosaic {Z.shape}, lon {X.min():.2f}..{X.max():.2f}, lat {Y.max():.2f}..{Y.min():.2f}, nan={np.isnan(Z).sum()}")
gx = np.linspace(X.min(), X.max(), int((X.max()-X.min())/0.01))
gy = np.linspace(Y.max(), Y.min(), int((Y.max()-Y.min())/0.01))
itp = RegularGridInterpolator((Y,X), Z, bounds_error=False, fill_value=np.nan)
GY,GX = np.meshgrid(gy,gx,indexing="ij")
ZZ = itp(np.stack([GY.ravel(),GX.ravel()],axis=1)).reshape(GY.shape)
print(f"  DEM {ZZ.shape}  z {np.nanmin(ZZ):.0f}..{np.nanmax(ZZ):.0f} m")

# transform DEM lon/lat -> EPSG:4547 for overlay
from pyproj import Transformer
tr = Transformer.from_crs(4326, EPSG, always_xy=True)
px, py = tr.transform(GX.ravel(), GY.ravel())
PX = np.array(px).reshape(ZZ.shape); PY = np.array(py).reshape(ZZ.shape)
mask = (PX>=hbp.total_bounds[0])&(PX<=hbp.total_bounds[2])&(PY>=hbp.total_bounds[1])&(PY<=hbp.total_bounds[3])
ZZm = np.where(mask, ZZ, np.nan)
print(f"  DEM cropped to province bbox, valid px {np.isfinite(ZZm).sum():,}")

# ---------- GENERALIZE + SYMBOLIZE ----------
def four_colour(gs, pal):
    n=len(gs); adj={i:set() for i in range(n)}
    for i in range(n):
        for j in range(i+1,n):
            if gs[i].touches(gs[j]) or gs[i].intersects(gs[j]): adj[i].add(j); adj[j].add(i)
    order=sorted(range(n),key=lambda i:len(adj[i]),reverse=True); asg={}
    for i in order:
        used={asg[j] for j in adj[i] if j in asg}; c=0
        while c in used: c+=1
        asg[i]=c
    return [pal[a] for a in asg.values()]

PAL=["#DCE9D5","#F2E2C4","#E5D8EC","#FBE0DA","#D8E6EE","#EFEDD4"]
cols = four_colour(list(hbp.geometry), PAL)
hbp["fill"]=cols
print(f"four-colour: {len(set(cols))} colours, adjacent-same=0")

# river widths (metres) -> true-width polygons
RW = {"长江":1400.0,"汉江":350.0,"汉水":350.0,"清江":220.0,"黄柏河":120.0,
      "香溪河":90.0,"沮河":150.0,"漳河":160.0,"滠水":110.0,"府河":90.0,
      "澴水":90.0,"内荆河":110.0,"东荆河":150.0,"唐白河":100.0,"汉北河":70.0}
rpoly=[]
for _,r in rivp.iterrows():
    nm=str(r["name"]).strip(); w=RW.get(nm,70.0)
    b=r.geometry.buffer(w/2.0, cap_style=1, join_style=1)
    rpoly.append((nm,b,w))
print(f"rivers -> {len(rpoly)} true-width polygons")

# ---------- COMPOSE ----------
fig = plt.figure(figsize=(11.5,10.0), dpi=150)
ax = fig.add_axes([0.045,0.055,0.91,0.845])
ax.set_facecolor("#FBFAF6")
x0,y0,x1,y1 = hbp.total_bounds
x0-=(x1-x0)*0.035; x1+=(x1-x0)*0.035; y0-=(y1-y0)*0.035; y1+=(y1-y0)*0.035

cm = LinearSegmentedColormap.from_list("hyp",[(0.00,"#C3E0B8"),(0.15,"#D9E9BE"),
    (0.32,"#EDEFBE"),(0.52,"#E9D69C"),(0.74,"#D3A972"),(1.00,"#A56F4B")],N=256)
ls = LightSource(azdeg=315, altdeg=45)
zfill = float(np.nanmin(ZZm))
rgb = ls.shade(np.nan_to_num(ZZm, nan=zfill), cmap=cm, blend_mode="soft",
               vert_exag=2.2, vmin=0, vmax=float(np.nanpercentile(ZZm,99)))
# clip the terrain raster to the province outline (no wash outside Hubei)
from matplotlib.path import Path
from matplotlib.patches import PathPatch
prov_geom = hbp.geometry.union_all()
prov_path = Path(np.asarray(prov_geom.exterior.coords)) if prov_geom.geom_type=="Polygon" else None
clip_patch = None
if prov_path is not None:
    clip_patch = PathPatch(prov_path, facecolor="none", edgecolor="none", zorder=6)
    ax.add_patch(clip_patch)
    im = ax.imshow(rgb, extent=(PX.min(),PX.max(),PY.min(),PY.max()), origin="upper",
                   aspect="auto", zorder=5, alpha=0.92)
    im.set_clip_path(clip_patch)
else:
    ax.imshow(rgb, extent=(PX.min(),PX.max(),PY.min(),PY.max()), origin="upper",
              aspect="auto", zorder=5, alpha=0.92)

# admin fill (over terrain)
for geom,c in zip(hbp.geometry,hbp["fill"]):
    for p in (geom.geoms if geom.geom_type=="MultiPolygon" else [geom]):
        ax.fill(*p.exterior.xy, facecolor=c, edgecolor="none", zorder=10, alpha=0.86)
        for r_ in p.interiors:
            ax.fill(*r_.xy, facecolor="#FBFAF6", edgecolor="none", zorder=10, alpha=0.86)

# rivers
for nm,b,w in rpoly:
    for p in (b.geoms if b.geom_type=="MultiPolygon" else [b]):
        ax.fill(*p.exterior.xy, facecolor="#A8D4EE", edgecolor="#4E90C8", lw=0.8, zorder=20)

# boundaries
bb = gpd.GeoDataFrame(geometry=hbp.geometry.boundary, crs=hbp.crs)
bb.plot(ax=ax, color="#C9A0DC", lw=4.2, alpha=0.38, zorder=30)
bb.plot(ax=ax, color="#6B4E8F", lw=1.05, linestyle=(0,(5,3)), zorder=31)
prov = gpd.GeoDataFrame(geometry=[hbp.geometry.union_all().boundary], crs=hbp.crs)
prov.plot(ax=ax, color="#8A5FBF", lw=5.0, alpha=0.40, zorder=32)
prov.plot(ax=ax, color="#3D2470", lw=2.0, linestyle=(0,(9,3,2,3)), zorder=33)

# labels
boxes=[]
labels=[]
for _,r in hbp.iterrows():
    p=r.geometry.representative_point()
    labels.append((r["name_cn"], p.x, p.y))
def place(txt,x,y,size=10.5,color="#243044",weight="normal"):
    w=len(txt)*size*0.95
    bb_=(x-w/2,y-size*0.7,x+w/2,y+size*0.7)
    for o in boxes:
        if bb_[0]<o[2] and bb_[2]>o[0] and bb_[1]<o[3] and bb_[3]>o[1]: return False
    boxes.append(bb_)
    ax.text(x,y,txt,fontfamily=FONT,fontsize=size,ha="center",va="center",color=color,
            zorder=60,fontweight=weight,path_effects=[pe.withStroke(linewidth=3.2,foreground="#FFFFFF")])
    return True
for t,x,y in sorted(labels,key=lambda b:-len(b[0])):
    place(t,x,y,size=11.5 if len(t)>3 else 10)

W = hbp[hbp["name_cn"]=="武汉"].iloc[0]
cx,cy = W.geometry.representative_point().x, W.geometry.representative_point().y
ax.plot([cx],[cy],marker="*",markersize=19,color="#C8102E",zorder=70,
        markeredgecolor="white",markeredgewidth=1.2)
place("武汉", cx+20000, cy+11000, size=11.5, color="#C8102E", weight="bold")

# river labels along the polyline
for target in ["长江","汉江"]:
    cand=[(nm,b) for nm,b,_ in rpoly if nm==target]
    if not cand: continue
    best=max(cand,key=lambda t:t[1].area)
    p=best[1].representative_point()
    ax.text(p.x,p.y,"长  江" if target=="长江" else "汉  江",fontfamily=FONT,fontsize=10.5,
            color="#1D4ED8",ha="center",va="center",zorder=65,style="italic",
            path_effects=[pe.withStroke(linewidth=3.0,foreground="#FFFFFF")])

ax.set_xlim(x0,x1); ax.set_ylim(y0,y1); ax.set_aspect("equal"); ax.set_axis_off()
for sp in ax.spines.values(): sp.set_edgecolor("#1A1A1A"); sp.set_linewidth(2.4)

# graticule (1 degree)
for gxv in np.arange(np.floor(x0/100000)*100000, x1, 100000):
    if x0<gxv<x1: ax.axvline(gxv,color="#4A4A4A",lw=0.35,ls=(0,(6,6)),alpha=0.30,zorder=4)
for gyv in np.arange(np.floor(y0/100000)*100000, y1, 100000):
    if y0<gyv<y1: ax.axhline(gyv,color="#4A4A4A",lw=0.35,ls=(0,(6,6)),alpha=0.30,zorder=4)

ax.text(0.5,1.048,"湖 北 省 行 政 区 划 图",transform=ax.transAxes,fontfamily=FONT,
        fontsize=20,fontweight="bold",color="#111111",ha="center",va="bottom",zorder=100)
ax.text(0.5,1.012,"Administrative Division Map of Hubei Province, China",
        transform=ax.transAxes,fontfamily=SANS,fontsize=10,color="#444444",ha="center",va="bottom",zorder=100)

# scale bar 4 alternating
sx0,sy0 = x0+(x1-x0)*0.04, y0+(y1-y0)*0.028
seg=(x1-x0)*0.082; sh=(y1-y0)*0.0085
ax.add_patch(mpatches.Rectangle((sx0,sy0),seg,sh,facecolor="#111",edgecolor="#111",lw=0.7,zorder=100))
ax.add_patch(mpatches.Rectangle((sx0+seg,sy0),seg,sh,facecolor="#FFF",edgecolor="#111",lw=0.7,zorder=100))
ax.add_patch(mpatches.Rectangle((sx0+2*seg,sy0),seg,sh,facecolor="#111",edgecolor="#111",lw=0.7,zorder=100))
ax.add_patch(mpatches.Rectangle((sx0+3*seg,sy0),seg,sh,facecolor="#FFF",edgecolor="#111",lw=0.7,zorder=100))
for i in range(5):
    ax.plot([sx0+seg*i]*2,[sy0,sy0+sh],color="#111",lw=0.7,zorder=101)
for i,lab in enumerate(["0","100","200","300","400 km"]):
    ax.text(sx0+seg*i,sy0-sh*1.3,lab,fontfamily=SANS,fontsize=7.4,color="#111",
            ha="center",va="top",zorder=101)

# legend
lx,ly = x1-(x1-x0)*0.225, y1-(y1-y0)*0.285
lw,lh = (x1-x0)*0.205,(y1-y0)*0.225
ax.add_patch(mpatches.FancyBboxPatch((lx,ly),lw,lh,boxstyle="round,pad=0.004",
             facecolor="#FFFFFF",edgecolor="#555",lw=0.9,alpha=0.95,zorder=100))
ax.text(lx+lw/2,ly+lh-0.016*(y1-y0),"图  例",fontfamily=FONT,fontsize=10.5,fontweight="bold",
        ha="center",va="top",zorder=101)
rows=[("省  界","line",(0,(9,3,2,3)),"#3D2470"),("市  界","line",(0,(5,3)),"#6B4E8F"),
      ("长  江","poly",None,"#A8D4EE"),("省级行政中心","star",None,"#C8102E"),
      ("高程分层设色","ramp",None,None)]
yy=ly+lh-0.052*(y1-y0)
for label,kind,ls_,col in rows:
    if kind=="line": ax.plot([lx+0.012*lw,lx+0.05*lw],[yy,yy],color=col,lw=2.0,ls=ls_,zorder=101)
    elif kind=="poly": ax.add_patch(mpatches.Rectangle((lx+0.013*lw,yy-0.006*(y1-y0)),0.032*lw,0.012*(y1-y0),facecolor=col,edgecolor="#4E90C8",lw=0.7,zorder=101))
    elif kind=="star": ax.plot([lx+0.029*lw],[yy],marker="*",markersize=14,color=col,zorder=101)
    elif kind=="ramp":
        n=60
        for i in range(n):
            ax.add_patch(mpatches.Rectangle((lx+0.013*lw+i*0.031*lw/n,yy-0.006*(y1-y0)),
                         0.031*lw/n,0.012*(y1-y0),facecolor=cm(0.05+0.9*i/n),edgecolor="none",zorder=101))
    ax.text(lx+0.055*lw,yy,label,fontfamily=FONT,fontsize=8.0,va="center",zorder=101)
    yy-=0.031*(y1-y0)

ax.text(0.5,-0.032,"数据来源：GADM 4.1（省级行政区划）· 水系：OpenStreetMap (ODbL) · 高程：SRTM 30m (NASA)    |    "
    "投影：CGCS2000 高斯-克吕格 3°带 CM 114°E (EPSG:4547)    |    制图：Carto-Agent 地图制图智能体",
    transform=ax.transAxes,fontfamily=FONT,fontsize=7.2,color="#555555",ha="center",va="top",zorder=100)

out=os.path.join(GEO,"REFERENCE_hubei_admin_v2.png")
fig.savefig(out,dpi=150,facecolor="white",bbox_inches="tight",pad_inches=0.2)
plt.close(fig)
print("wrote",out,os.path.getsize(out)//1024,"KB")
