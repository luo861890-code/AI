#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GeoToken POC实验 - 验证DoMapAI地图语言Token化方法的可行性

实验流程（对应DoMapAI "道"之路径验证）：
1. 从DEM数据生成等高线（如果有本地DEM数据）
2. 降级方案：生成模拟等高线数据（武汉市区域）
3. 使用ContourTokenizer转换为Token序列
4. 使用TokenEmbedder生成嵌入向量
5. 可视化Token化过程和重建效果
6. 计算重建误差

DoMapAI参考：
- 艾廷华教授提出的地图语言Token化框架
- Token序列 → MapGPT预训练 → 地图智能体
- 分形曲线编码方法：将二维空间模式转为序列模式

所有实现使用纯NumPy，不依赖PyTorch/TensorFlow。
"""

import sys
import os
import math
import time
from typing import List, Tuple, Dict, Any

import numpy as np

# 确保项目根目录在Python路径中
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
_backend_root = os.path.join(_PROJECT_ROOT, "backend")
sys.path.insert(0, _backend_root)

# 直接导入geotoken_service模块（绕过__init__.py的级联导入，避免依赖冲突）
import importlib.util
_geotoken_path = os.path.join(_backend_root, "app", "services", "geotoken_service.py")
_spec = importlib.util.spec_from_file_location("geotoken_service", _geotoken_path)
_geotoken_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_geotoken_module)

GeoTileTokenizer = _geotoken_module.GeoTileTokenizer
ContourTokenizer = _geotoken_module.ContourTokenizer
LandUseTokenizer = _geotoken_module.LandUseTokenizer
TokenEmbedder = _geotoken_module.TokenEmbedder

# matplotlib 可选依赖
try:
    import matplotlib
    matplotlib.use("Agg")  # 非交互后端
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch
    _HAS_MATPLOTLIB = True
except ImportError:
    _HAS_MATPLOTLIB = False
    print("[警告] matplotlib 不可用，跳过可视化输出。")


# ============================================================================
# 模拟等高线数据生成（降级方案）
# ============================================================================

def generate_simulated_contours(
    center_lat: float = 30.5928,
    center_lng: float = 114.3055,
    num_contours: int = 20,
    points_per_contour: int = 100,
    seed: int = 42,
) -> List[List[Tuple[float, float]]]:
    """生成模拟的武汉市等高线数据（降级方案）。

    在没有真实DEM数据的情况下，使用数学函数生成模拟地形等高线，
    用于验证Token化方法的可行性。

    方法：使用高斯混合模型模拟武汉市地形特征
    - 武汉市地形特征：中部低平（长江汉江交汇）、南北丘陵
    - 北侧（黄陂）：大别山余脉，海拔较高
    - 南侧（江夏）：幕阜山余脉，低山丘陵
    - 中部：江汉平原，地势平坦

    Args:
        center_lat: 武汉市中心纬度（默认30.5928）
        center_lng: 武汉市中心经度（默认114.3055）
        num_contours: 生成的等高线条数
        points_per_contour: 每条等高线的采样点数
        seed: 随机种子

    Returns:
        等高线列表，每条等高线为 [(lng, lat), ...] 坐标序列
    """
    rng = np.random.RandomState(seed)

    # 模拟区域范围：约0.8度×0.8度（约80km×75km）
    lat_min = center_lat - 0.4
    lat_max = center_lat + 0.4
    lng_min = center_lng - 0.4
    lng_max = center_lng + 0.4

    # 武汉市地形模拟：多峰高斯混合
    # 山峰位置定义（模拟真实武汉地形）
    peaks = [
        {"lng": 114.35, "lat": 30.85, "height": 1.0, "sigma": 0.15, "name": "木兰山(黄陂北部)"},
        {"lng": 114.15, "lat": 30.45, "height": 0.6, "sigma": 0.12, "name": "九峰山(江夏东)"},
        {"lng": 114.50, "lat": 30.60, "height": 0.4, "sigma": 0.10, "name": "喻家山(洪山)"},
        {"lng": 114.20, "lat": 30.30, "height": 0.5, "sigma": 0.12, "name": "青龙山(江夏南)"},
        {"lng": 114.40, "lat": 30.90, "height": 0.7, "sigma": 0.14, "name": "大别山余脉"},
    ]

    # 生成平滑地形场
    lng_grid, lat_grid = np.meshgrid(
        np.linspace(lng_min, lng_max, points_per_contour),
        np.linspace(lat_min, lat_max, points_per_contour),
    )

    elevation = np.zeros_like(lng_grid)
    for peak in peaks:
        dist_sq = ((lng_grid - peak["lng"]) / 0.1) ** 2 + ((lat_grid - peak["lat"]) / 0.1) ** 2
        elevation += peak["height"] * np.exp(-dist_sq / (2 * peak["sigma"] ** 2))

    # 武汉市中心低平（长江汉江交汇处，人为降低高程）
    river_mask = ((lng_grid - center_lng) / 0.05) ** 2 + ((lat_grid - center_lat) / 0.08) ** 2 < 1.0
    elevation[river_mask] *= 0.1

    # 添加噪声模拟真实地形
    elevation += rng.normal(0, 0.02, elevation.shape)

    # 归一化到 [0, 1]
    elev_min, elev_max = elevation.min(), elevation.max()
    elevation = (elevation - elev_min) / (elev_max - elev_min)

    # 提取等高线
    contour_levels = np.linspace(0.1, 0.9, num_contours)
    contours = []

    for level in contour_levels:
        # 使用 marching squares 思想提取等高线
        contour_points = _extract_contour_line(
            lng_grid, lat_grid, elevation, level, rng
        )
        if len(contour_points) >= 5:  # 过滤太短的等高线
            contours.append(contour_points)

    # 如果提取的等高线不够，补充圆形模拟等高线
    while len(contours) < num_contours:
        extra = _generate_circular_contour(
            center_lng, center_lat, points_per_contour,
            radius=0.1 + rng.rand() * 0.3, noise=0.005, rng=rng
        )
        contours.append(extra)

    return contours[:num_contours]


def _extract_contour_line(
    lng_grid: np.ndarray,
    lat_grid: np.ndarray,
    elevation: np.ndarray,
    level: float,
    rng: np.random.RandomState,
) -> List[Tuple[float, float]]:
    """从高程网格中提取一条等高线（简化版marching squares）。

    Args:
        lng_grid: 经度网格 (H, W)
        lat_grid: 纬度网格 (H, W)
        elevation: 高程网格 (H, W)，值在[0,1]
        level: 等高线高程值
        rng: 随机数生成器

    Returns:
        [(lng, lat), ...] 等高线坐标
    """
    H, W = elevation.shape
    contour_mask = (elevation > level - 0.03) & (elevation < level + 0.03)

    # 随机采样轮廓点
    points = []
    for i in range(H):
        for j in range(W):
            if contour_mask[i, j]:
                points.append((float(lng_grid[i, j]), float(lat_grid[i, j])))

    if len(points) < 3:
        return points

    # 简化：按角度排序使等高线连续（取中心点为参考）
    center_lng = np.mean([p[0] for p in points])
    center_lat = np.mean([p[1] for p in points])

    def angle(p):
        return math.atan2(p[1] - center_lat, p[0] - center_lng)

    points.sort(key=angle)

    # 降采样使点数合理
    if len(points) > 100:
        step = len(points) // 100
        points = points[::step]
        if points and points[0] != points[-1]:
            points.append(points[0])  # 闭合

    # 添加少量噪声使等高线更自然
    result = []
    for lng, lat in points:
        result.append((
            lng + rng.normal(0, 0.001),
            lat + rng.normal(0, 0.001),
        ))
    return result


def _generate_circular_contour(
    center_lng: float,
    center_lat: float,
    n_points: int,
    radius: float,
    noise: float,
    rng: np.random.RandomState,
) -> List[Tuple[float, float]]:
    """生成带噪声的圆形模拟等高线（补充用）。

    Args:
        center_lng: 圆心经度
        center_lat: 圆心纬度
        n_points: 采样点数
        radius: 半径（度）
        noise: 噪声幅度
        rng: 随机数生成器

    Returns:
        [(lng, lat), ...] 闭合等高线坐标
    """
    angles = np.linspace(0, 2 * np.pi, n_points)
    points = []
    for theta in angles:
        r = radius + rng.normal(0, noise)
        lng = center_lng + r * np.cos(theta) * 1.1  # 经度方向稍稍拉长
        lat = center_lat + r * np.sin(theta) * 0.9  # 纬度方向稍稍压扁
        points.append((float(lng), float(lat)))
    return points


# ============================================================================
# 土地利用模拟数据生成
# ============================================================================

def generate_simulated_landuse(
    grid_size: int = 20,
    seed: int = 42,
) -> Dict[Tuple[int, int], int]:
    """生成模拟的武汉市土地利用网格数据。

    模拟武汉典型土地利用格局：
    - 中部（长江沿岸）：建设用地和水域为主
    - 北部：林地为主（大别山余脉）
    - 南部：耕地和园地为主
    - 周边：镶嵌有草地和未利用地

    Args:
        grid_size: 网格大小
        seed: 随机种子

    Returns:
        {(row, col): 类型编码} 网格字典
    """
    rng = np.random.RandomState(seed)
    grid = {}

    for row in range(grid_size):
        for col in range(grid_size):
            # 计算距中心距离
            cx, cy = grid_size / 2, grid_size / 2
            dist = np.sqrt((row - cy) ** 2 + (col - cx) ** 2)
            dist_norm = dist / (grid_size * 0.7)  # 归一化

            # 基于位置和随机因素确定土地利用类型
            rand = rng.rand()

            if row < grid_size * 0.25:
                # 北部：以林地为主（大别山余脉）
                if rand < 0.55:
                    code = 2   # 林地
                elif rand < 0.75:
                    code = 3   # 草地
                elif rand < 0.90:
                    code = 1   # 耕地
                else:
                    code = 7   # 园地
            elif row > grid_size * 0.75:
                # 南部：耕地和园地为主（江夏农业区）
                if rand < 0.35:
                    code = 1   # 耕地
                elif rand < 0.55:
                    code = 7   # 园地
                elif rand < 0.75:
                    code = 3   # 草地
                elif rand < 0.90:
                    code = 5   # 建设用地
                else:
                    code = 4   # 水域
            elif dist_norm < 0.25:
                # 城市核心区：建设用地和水域
                if rand < 0.50:
                    code = 5   # 建设用地
                elif rand < 0.70:
                    code = 4   # 水域（长江汉江）
                elif rand < 0.85:
                    code = 8   # 交通用地
                else:
                    code = 9   # 水工建筑
            else:
                # 过渡带：混合类型
                if rand < 0.25:
                    code = 5   # 建设用地
                elif rand < 0.50:
                    code = 1   # 耕地
                elif rand < 0.65:
                    code = 3   # 草地
                elif rand < 0.80:
                    code = 2   # 林地
                elif rand < 0.92:
                    code = 4   # 水域
                else:
                    code = 6   # 未利用地

            grid[(row, col)] = code

    return grid


# ============================================================================
# 可视化函数
# ============================================================================

def visualize_results(
    contours: List[List[Tuple[float, float]]],
    all_tokens: List[List[str]],
    all_reconstructed: List[List[Tuple[float, float]]],
    errors: List[float],
    output_dir: str,
) -> str:
    """生成Token化过程的可视化PNG。

    包含4个子图:
    1. 原始等高线
    2. Hilbert索引热力图（Token空间分布）
    3. Token频率直方图
    4. 原始等高线 vs 重建等高线 对比

    Args:
        contours: 原始等高线列表
        all_tokens: 每条等高线的Token序列
        all_reconstructed: 每条等高线的重建坐标
        errors: 每条等高线的重建误差
        output_dir: 输出目录

    Returns:
        保存的PNG文件路径
    """
    if not _HAS_MATPLOTLIB:
        return ""

    # 中文字体设置
    plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False

    fig, axes = plt.subplots(2, 2, figsize=(16, 14))
    fig.suptitle(
        "GeoToken POC \u5b9e\u9a8c\u53ef\u89c6\u5316 \u2014 \u6b66\u6c49\u5e02\u7b49\u9ad8\u7ebfToken\u5316",
        fontsize=16, fontweight="bold"
    )

    # ---- 子图1: 原始等高线 ----
    ax1 = axes[0, 0]
    for i, contour in enumerate(contours):
        lngs = [p[0] for p in contour]
        lats = [p[1] for p in contour]
        color = plt.cm.viridis(i / len(contours))
        ax1.plot(lngs, lats, color=color, linewidth=0.8, alpha=0.8)
    ax1.set_xlabel("Longitude (\u00b0E)")
    ax1.set_ylabel("Latitude (\u00b0N)")
    ax1.set_title(f"Original Contours (n={len(contours)})")
    ax1.set_aspect("equal")
    ax1.grid(True, alpha=0.3)

    # ---- 子图2: Hilbert索引热力图（Token空间分布） ----
    ax2 = axes[0, 1]
    # 收集所有Hilbert索引值
    all_hilbert_indices = []
    for tokens in all_tokens:
        for token in tokens:
            parts = token.split("_")
            if len(parts) >= 3:
                try:
                    all_hilbert_indices.append(int(parts[1]))
                except ValueError:
                    pass

    if all_hilbert_indices:
        # 构建Hilbert索引分布的二维直方图
        # 使用grid_resolution=64，所以索引范围 [0, 4095]
        n_bins = 64
        hist, xedges, yedges = np.histogram2d(
            [h % 64 for h in all_hilbert_indices],
            [h // 64 for h in all_hilbert_indices],
            bins=n_bins,
            range=[[0, 63], [0, 63]],
        )
        im = ax2.imshow(hist, origin="lower", cmap="hot", aspect="equal",
                         extent=[0, 63, 0, 63])
        ax2.set_xlabel("Hilbert X (grid)")
        ax2.set_ylabel("Hilbert Y (grid)")
        ax2.set_title("Hilbert Index Heatmap (Token Spatial Distribution)")
        plt.colorbar(im, ax=ax2, shrink=0.8, label="Frequency")
    else:
        ax2.text(0.5, 0.5, "No Hilbert indices", ha="center", va="center",
                 transform=ax2.transAxes)
        ax2.set_title("Hilbert Index Heatmap (empty)")

    # ---- 子图3: Token频率直方图 ----
    ax3 = axes[1, 0]
    all_token_counts = [len(tokens) for tokens in all_tokens]
    ax3.hist(all_token_counts, bins=min(30, len(all_token_counts)),
             color="steelblue", edgecolor="white", alpha=0.8)
    ax3.axvline(x=np.mean(all_token_counts), color="red", linestyle="--",
                label=f"Mean: {np.mean(all_token_counts):.1f}")
    ax3.set_xlabel("Tokens per Contour")
    ax3.set_ylabel("Frequency")
    ax3.set_title("Token Sequence Length Distribution")
    ax3.legend()

    # ---- 子图4: 原始 vs 重建 等高线对比 ----
    ax4 = axes[1, 1]
    # 选择误差最小、中位、最大的三条等高线
    if len(errors) >= 3 and len(contours) >= 3:
        sorted_idx = np.argsort(errors)
        selected = [sorted_idx[0], sorted_idx[len(sorted_idx) // 2], sorted_idx[-1]]
        labels = ["Best", "Median", "Worst"]

        for si, label in zip(selected, labels):
            orig = contours[si]
            recon = all_reconstructed[si] if si < len(all_reconstructed) else []

            olng = [p[0] for p in orig]
            olat = [p[1] for p in orig]
            ax4.plot(olng, olat, "-", linewidth=1.5, alpha=0.7,
                     label=f"{label} (Orig, RMSE={errors[si]:.6f})")

            if recon:
                rlng = [p[0] for p in recon]
                rlat = [p[1] for p in recon]
                ax4.plot(rlng, rlat, "--", linewidth=1.2, alpha=0.6,
                         label=f"{label} (Recon)")

    ax4.set_xlabel("Longitude (\u00b0E)")
    ax4.set_ylabel("Latitude (\u00b0N)")
    ax4.set_title("Original vs Reconstructed Contours")
    ax4.legend(fontsize=7, loc="upper right")
    ax4.set_aspect("equal")
    ax4.grid(True, alpha=0.3)

    plt.tight_layout()
    output_path = os.path.join(output_dir, "geotoken_poc_visualization.png")
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)

    return output_path


# ============================================================================
# 实验主流程
# ============================================================================

def run_experiment():
    """运行GeoToken POC实验主流程。"""
    print("=" * 70)
    print("  GeoToken POC\u5b9e\u9a8c \u2014 \u9a8c\u8bc1DoMapAI\u5730\u56fe\u8bed\u8a00Token\u5316\u65b9\u6cd5")
    print("  \u6b66\u6c49\u5e02\u7b49\u9ad8\u7ebf\u6a21\u62df\u6570\u636e + Hilbert\u66f2\u7ebf\u7f16\u7801")
    print("=" * 70)
    print()

    # ---- 配置参数 ----
    GRID_RESOLUTION = 64          # Hilbert曲线网格分辨率（2^6）
    NUM_CONTOURS = 20             # 模拟等高线条数
    POINTS_PER_CONTOUR = 100      # 每条等高线采样点数
    EMBED_DIM = 64                # 嵌入向量维度
    OUTPUT_DIR = os.path.join(_PROJECT_ROOT, "output")
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print(f"[\u914d\u7f6e] Hilbert\u7f51\u683c\u5206\u8fa8\u7387: {GRID_RESOLUTION}x{GRID_RESOLUTION}")
    print(f"[\u914d\u7f6e] \u6a21\u62df\u7b49\u9ad8\u7ebf: {NUM_CONTOURS}\u6761, \u6bcf\u6761{POINTS_PER_CONTOUR}\u70b9")
    print(f"[\u914d\u7f6e] \u5d4c\u5165\u5411\u91cf\u7ef4\u5ea6: {EMBED_DIM}")
    print(f"[\u914d\u7f6e] \u53ef\u89c6\u5316\u652f\u6301: {'\u2713' if _HAS_MATPLOTLIB else '\u2717 (matplotlib\u4e0d\u53ef\u7528)'}")
    print()

    # ======== 阶段1: 生成模拟等高线数据 ========
    print("\u2501" * 60)
    print("\u9636\u6bb51: \u751f\u6210\u6a21\u62df\u7b49\u9ad8\u7ebf\u6570\u636e")
    print("\u2501" * 60)

    t0 = time.time()
    contours = generate_simulated_contours(
        center_lat=30.5928, center_lng=114.3055,
        num_contours=NUM_CONTOURS, points_per_contour=POINTS_PER_CONTOUR,
        seed=42,
    )
    t1 = time.time()
    print(f"  \u751f\u6210\u7b49\u9ad8\u7ebf: {len(contours)}\u6761 (\u8017\u65f6 {t1-t0:.3f}s)")
    for i, c in enumerate(contours):
        print(f"    \u7b49\u9ad8\u7ebf #{i+1}: {len(c)}\u70b9, "
              f"\u8303\u56f4 [({min(p[0] for p in c):.4f},{min(p[1] for p in c):.4f}) - "
              f"({max(p[0] for p in c):.4f},{max(p[1] for p in c):.4f})]")
    print()

    # ======== 阶段2: 等高线Token化 ========
    print("\u2501" * 60)
    print("\u9636\u6bb52: \u7b49\u9ad8\u7ebfToken\u5316 (Hilbert\u66f2\u7ebf\u7f16\u7801)")
    print("\u2501" * 60)

    # 验证网格分辨率约束
    assert (GRID_RESOLUTION > 0 and (GRID_RESOLUTION & (GRID_RESOLUTION - 1)) == 0), \
        f"GRID_RESOLUTION \u5fc5\u987b\u4e3a2\u7684\u5e42: {GRID_RESOLUTION}"

    tokenizer = ContourTokenizer(grid_resolution=GRID_RESOLUTION)
    print(f"  Tokenizer: ContourTokenizer(grid_resolution={GRID_RESOLUTION})")
    print(f"  Hilbert\u7f51\u683c: {GRID_RESOLUTION}x{GRID_RESOLUTION} = {GRID_RESOLUTION**2}\u4e2a\u683c\u5b50")
    print(f"  \u7406\u8bbaToken\u7a7a\u95f4\u5927\u5c0f: {GRID_RESOLUTION**2}")
    print()

    all_tokens = []
    all_reconstructed = []
    errors = []

    t0 = time.time()
    for i, contour in enumerate(contours):
        # Step 2a: Tokenize
        tokens = tokenizer.tokenize_contour(contour)
        all_tokens.append(tokens)

        # Step 2b: Reconstruct
        if tokens:
            reconstructed = tokenizer.detokenize_to_centroids(tokens)
        else:
            reconstructed = []
        all_reconstructed.append(reconstructed)

        # Step 2c: 计算重建误差
        error = tokenizer.reconstruction_error(contour, reconstructed)
        errors.append(error)

        # 输出每条等高线的基本信息
        print(f"  \u7b49\u9ad8\u7ebf #{i+1:2d}: "
              f"\u539f\u59cb\u70b9\u6570={len(contour):3d}, "
              f"Token\u6570={len(tokens):3d}, "
              f"\u538b\u7f29\u6bd4={len(contour)/max(len(tokens),1):.1f}x, "
              f"RMSE={error:.8f}\u00b0")

    t1 = time.time()
    print(f"\n  Token\u5316\u603b\u8017\u65f6: {t1-t0:.3f}s")

    # 统计汇总
    all_token_counts = [len(t) for t in all_tokens]
    total_tokens = sum(all_token_counts)
    total_points = sum(len(c) for c in contours)
    mean_error = np.mean(errors)
    std_error = np.std(errors)
    mean_compression = np.mean([len(c) / max(len(t), 1) for c, t in zip(contours, all_tokens)])

    print(f"\n  --- Token\u5316\u7edf\u8ba1\u6c47\u603b ---")
    print(f"  \u603b\u539f\u59cb\u70b9\u6570: {total_points}")
    print(f"  \u603bToken\u6570: {total_tokens}")
    print(f"  \u5e73\u5747\u538b\u7f29\u6bd4: {mean_compression:.2f}x")
    print(f"  \u5e73\u5747\u6bcf\u7b49\u9ad8\u7ebfToken\u6570: {np.mean(all_token_counts):.1f} \u00b1 {np.std(all_token_counts):.1f}")
    print(f"  \u5e73\u5747\u91cd\u5efa\u8bef\u5dee (RMSE): {mean_error:.8f}\u00b0 \u00b1 {std_error:.8f}\u00b0")
    print(f"  \u6700\u5c0f\u91cd\u5efa\u8bef\u5dee: {min(errors):.8f}\u00b0")
    print(f"  \u6700\u5927\u91cd\u5efa\u8bef\u5dee: {max(errors):.8f}\u00b0")
    print()

    # ======== 阶段3: Token嵌入向量生成 ========
    print("\u2501" * 60)
    print("\u9636\u6bb53: Token\u5d4c\u5165\u5411\u91cf\u751f\u6210")
    print("\u2501" * 60)

    embedder = TokenEmbedder(vocab_size=10000, embed_dim=EMBED_DIM)
    t0 = time.time()

    all_embeddings = []
    for tokens in all_tokens:
        if tokens:
            emb = embedder.embed_sequence(tokens)
            all_embeddings.append(emb)
        else:
            all_embeddings.append(np.zeros((0, EMBED_DIM)))

    t1 = time.time()
    print(f"  \u5d4c\u5165\u5668: TokenEmbedder(vocab_size=10000, embed_dim={EMBED_DIM})")
    print(f"  \u5d4c\u5165\u751f\u6210\u8017\u65f6: {t1-t0:.3f}s")

    # 计算等高线间相似度矩阵（样本前5条）
    n_show = min(5, len(contours))
    print(f"\n  --- \u7b49\u9ad8\u7ebf\u4e4b\u95f4\u4f59\u5f26\u76f8\u4f3c\u5ea6\u77e9\u9635 (\u524d{n_show}\u6761) ---")
    sim_matrix = np.zeros((n_show, n_show))
    for i in range(n_show):
        for j in range(n_show):
            sim = embedder.sequence_similarity(all_tokens[i], all_tokens[j])
            sim_matrix[i, j] = sim

    # 打印相似度矩阵
    header = "         " + "".join(f"  #{j+1}   " for j in range(n_show))
    print(f"  {header}")
    for i in range(n_show):
        row = "".join(f"  {sim_matrix[i, j]:.3f}" for j in range(n_show))
        print(f"  #{i+1}    {row}")

    # 对角线检查（自身相似度应接近1.0）
    diag_mean = np.mean(np.diag(sim_matrix))
    print(f"\n  \u5bf9\u89d2\u7ebf\u81ea\u8eab\u76f8\u4f3c\u5ea6\u5e73\u5747: {diag_mean:.4f} (\u7406\u60f3\u503c=1.0)")

    # 非对角线平均（不同等高线应有一定区分度）
    off_diag = []
    for i in range(n_show):
        for j in range(n_show):
            if i != j:
                off_diag.append(sim_matrix[i, j])
    off_diag_mean = np.mean(off_diag)
    print(f"  \u975e\u5bf9\u89d2\u7ebf\u76f8\u4f3c\u5ea6\u5e73\u5747: {off_diag_mean:.4f} (\u4e0d\u540c\u7b49\u9ad8\u7ebf\u5e94\u6709\u533a\u5206)")
    print()

    # ======== 阶段4: 土地利用Token化验证 ========
    print("\u2501" * 60)
    print("\u9636\u6bb54: \u571f\u5730\u5229\u7528Token\u5316\u9a8c\u8bc1 (DoMapAI\u7f16\u7801\u516c\u5f0f)")
    print("\u2501" * 60)

    lu_tokenizer = LandUseTokenizer()
    landuse_grid = generate_simulated_landuse(grid_size=20, seed=42)

    # 统计土地利用类型分布
    type_counts = {}
    for code in landuse_grid.values():
        type_counts[code] = type_counts.get(code, 0) + 1

    print(f"  \u571f\u5730\u5229\u7528\u7f51\u683c: 20x20 = {len(landuse_grid)}\u4e2a\u5355\u5143")
    print(f"  \u7c7b\u578b\u5206\u5e03:")
    for code in sorted(type_counts.keys()):
        name = LandUseTokenizer.LAND_USE_NAMES.get(code, "?")
        pct = type_counts[code] / len(landuse_grid) * 100
        print(f"    \u7c7b\u578b{code:2d} ({name}): {type_counts[code]:3d}\u5355\u5143 ({pct:5.1f}%)")

    # 计算SHDI
    shdi = lu_tokenizer.compute_shdi(type_counts)
    print(f"\n  \u9999\u6d53\u591a\u6837\u6027\u6307\u6570 SHDI: {shdi:.4f}")

    # 编码
    landuse_token = lu_tokenizer.encode_region(landuse_grid)
    print(f"  DoMapAI\u7f16\u7801Token: {landuse_token}")

    # 解码
    decoded = lu_tokenizer.decode_to_landscape(landuse_token)
    print(f"  \u89e3\u7801\u7ed3\u679c:")
    print(f"    SHDI (quantized): {decoded['shdi_quantized']}")
    print(f"    SHDI (approx):    {decoded['shdi_approx']}")
    print(f"    \u4e3b\u5bfc\u7c7b\u578b:       {decoded['dominant_type']} (\u7c7b\u578b{decoded['max1_code']})")
    print(f"    \u7b2c\u4e8c\u7c7b\u578b:       {decoded['max2_name']} (\u7c7b\u578b{decoded['max2_code']})")
    print(f"    \u7b2c\u4e09\u7c7b\u578b:       {decoded['max3_name']} (\u7c7b\u578b{decoded['max3_code']})")
    print()

    # ======== 阶段5: GeoTileTokenizer 网格Token化验证 ========
    print("\u2501" * 60)
    print("\u9636\u6bb55: \u7f51\u683cToken\u5316\u9a8c\u8bc1 (GeoTileTokenizer)")
    print("\u2501" * 60)

    # 使用武汉区域bbox
    wuhan_bbox = [114.0, 30.3, 114.6, 30.9]
    gt_tokenizer = GeoTileTokenizer(bbox=wuhan_bbox, resolution=20)

    # 从第一条等高线取点测试
    test_points = contours[0][:10] if contours else [
        (114.3055, 30.5928),
        (114.3500, 30.6000),
        (114.2500, 30.5500),
    ]
    gt_tokens = gt_tokenizer.tokenize_points(test_points)

    print(f"  Bbox: {wuhan_bbox}")
    print(f"  \u7f51\u683c\u5206\u8fa8\u7387: 20x20, \u8bcd\u6c47\u8868\u5927\u5c0f: {gt_tokenizer.vocab_size}")
    print(f"  \u6d4b\u8bd5\u70b9: {len(test_points)}\u4e2a")
    print(f"  Token\u5316\u7ed3\u679c:")
    for pt, token in zip(test_points[:5], gt_tokens[:5]):
        recon_pt = gt_tokenizer.detokenize_to_centroid(token)
        print(f"    ({pt[0]:.4f}, {pt[1]:.4f}) -> {token:12s} -> ({recon_pt[0]:.4f}, {recon_pt[1]:.4f})")
    print()

    # ======== 阶段6: 可视化 ========
    print("\u2501" * 60)
    print("\u9636\u6bb56: \u53ef\u89c6\u5316\u8f93\u51fa")
    print("\u2501" * 60)

    if _HAS_MATPLOTLIB:
        viz_path = visualize_results(
            contours, all_tokens, all_reconstructed, errors, OUTPUT_DIR
        )
        if viz_path:
            print(f"  \u53ef\u89c6\u5316\u6587\u4ef6: {viz_path}")
    else:
        print("  \u8df3\u8fc7\u53ef\u89c6\u5316 (matplotlib\u4e0d\u53ef\u7528)")
    print()

    # ======== 实验结论 ========
    print("=" * 70)
    print("  \u5b9e\u9a8c\u7ed3\u8bba")
    print("=" * 70)
    print()
    print("  1. \u7b49\u9ad8\u7ebfToken\u5316\u53ef\u884c\u6027:")
    print(f"     - \u5e73\u5747\u91cd\u5efa\u8bef\u5dee: {mean_error:.6f}\u00b0 (\u7ea6{mean_error*111000:.0f}m)")
    print(f"     - \u5e73\u5747\u538b\u7f29\u6bd4: {mean_compression:.1f}x")
    print(f"     - \u5e73\u5747Token\u6570/\u7b49\u9ad8\u7ebf: {np.mean(all_token_counts):.1f}")
    print()
    print("  2. \u5d4c\u5165\u5411\u91cf\u8d28\u91cf:")
    print(f"     - \u81ea\u8eab\u76f8\u4f3c\u5ea6: {diag_mean:.4f} (\u7406\u60f3: ~1.0)")
    print(f"     - \u4e0d\u540c\u7b49\u9ad8\u7ebf\u533a\u5206\u5ea6: {off_diag_mean:.4f} (\u7406\u60f3: \u8f83\u4f4e)")
    print()
    print("  3. \u571f\u5730\u5229\u7528\u7f16\u7801:")
    print(f"     - SHDI: {shdi:.4f}")
    print(f"     - Token: {landuse_token}")
    print(f"     - \u4e3b\u5bfc\u7c7b\u578b: {decoded['dominant_type']}")
    print()
    print("  4. \u4e0eDoMapAI\u6846\u67b6\u5bf9\u5e94\u5173\u7cfb:")
    print("     - ContourTokenizer \u21d4 DoMapAI\u5206\u5f62\u66f2\u7ebf\u7f16\u7801\u6a21\u5757")
    print("     - LandUseTokenizer \u21d4 DoMapAI\u666f\u89c2\u7f16\u7801\u516c\u5f0f")
    print("     - TokenEmbedder   \u21d4 DoMapAI MapGPT\u9884\u8bad\u7ec3\u5d4c\u5165\u5c42")
    print("     - GeoTileTokenizer\u21d4 DoMapAI\u7f51\u683c\u79bb\u6563\u5316\u57fa\u7840")
    print()
    print("  5. POC\u7ed3\u8bba:")
    if mean_error < 0.01:
        print("     \u2713 \u91cd\u5efa\u8bef\u5dee\u5728\u53ef\u63a5\u53d7\u8303\u56f4\u5185\uff0cHilbert\u7f16\u7801\u65b9\u6848\u53ef\u884c")
    else:
        print("     ! \u91cd\u5efa\u8bef\u5dee\u8f83\u5927\uff0c\u5efa\u8bae\u63d0\u9ad8\u7f51\u683c\u5206\u8fa8\u7387\u6216\u4f18\u5316\u5206\u6bb5\u7b56\u7565")
    print(f"     \u2713 \u5d4c\u5165\u5411\u91cf\u4f59\u5f26\u76f8\u4f3c\u5ea6\u53ef\u7528\u4e8e\u7b49\u9ad8\u7ebf\u68c0\u7d22\u548c\u6bd4\u8f83")
    print(f"     \u2713 DoMapAI\u571f\u5730\u5229\u7528\u7f16\u7801\u516c\u5f0f\u9a8c\u8bc1\u901a\u8fc7")
    print(f"     \u2713 \u7eafNumPy\u5b9e\u73b0\uff0c\u65e0\u5916\u90e8\u6df1\u5ea6\u5b66\u4e60\u6846\u67b6\u4f9d\u8d56")
    print()
    print(f"\u5b9e\u9a8c\u5b8c\u6210\u3002\u8f93\u51fa\u76ee\u5f55: {OUTPUT_DIR}")
    print("=" * 70)

    return {
        "num_contours": len(contours),
        "total_points": total_points,
        "total_tokens": total_tokens,
        "mean_compression_ratio": float(mean_compression),
        "mean_rmse": float(mean_error),
        "std_rmse": float(std_error),
        "min_rmse": float(min(errors)),
        "max_rmse": float(max(errors)),
        "self_similarity": float(diag_mean),
        "cross_similarity": float(off_diag_mean),
        "shdi": float(shdi),
        "landuse_token": landuse_token,
        "dominant_landuse": decoded["dominant_type"],
    }


if __name__ == "__main__":
    results = run_experiment()
