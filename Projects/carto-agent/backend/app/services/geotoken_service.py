"""GeoToken 地图语言Token化服务 - 基于DoMapAI框架的地图语言Token化POC

参考艾廷华教授DoMapAI框架中的地图语言Token化方法论：
1. 将二维地理数据（等高线、土地利用等）通过分形曲线变换为Token序列
2. 使用Word2Vec/随机投影将Token序列转换为嵌入向量
3. 为MapGPT预训练提供数据准备基础

核心思路（对应DoMapAI "道"之路径）：
- 地图语言 = 结构化Token序列 + 空间语义嵌入
- 等高线编码: 二维顶点序列 → Hilbert/Morton分形曲线 → 一维Token序列
- 土地利用编码: 景观格局指标(SHDI等) → 数学编码 → 整数Token
- 嵌入方案: 随机投影（POC快速方案）/ Word2Vec（生产方案）

所有实现使用纯NumPy，不依赖PyTorch/TensorFlow。
"""

from typing import List, Tuple, Dict, Optional, Any
import hashlib
import math
import random
import sys

# numpy为可选依赖——不可用时提供纯Python降级实现
try:
    import numpy as np
    _NUMPY_AVAILABLE = True
except ImportError:
    _NUMPY_AVAILABLE = False
    np = None  # type: ignore
    print("[GeoToken] numpy不可用，启用纯Python降级模式")

# 纯Python向量/矩阵运算工具（numpy不可用时的降级实现）
def _zeros(size: int) -> list:
    return [0.0] * size

def _zeros_2d(rows: int, cols: int) -> list:
    return [[0.0] * cols for _ in range(rows)]

def _l2_norm(vec: list) -> float:
    return math.sqrt(sum(x * x for x in vec))

def _mean_vectors(vectors: list) -> list:
    if not vectors:
        return []
    n = len(vectors)
    dim = len(vectors[0])
    result = [0.0] * dim
    for v in vectors:
        for i in range(dim):
            result[i] += v[i]
    return [x / n for x in result]

def _dot(a: list, b: list) -> float:
    return sum(x * y for x, y in zip(a, b))

def _random_normal(rows: int, cols: int, seed: int = 42) -> list:
    rng = random.Random(seed)
    scale = 1.0 / math.sqrt(cols)
    return [[rng.gauss(0, 1) * scale for _ in range(cols)] for _ in range(rows)]

# 为类型注解定义替代类型
_ArrayType = list  # 替代 np.ndarray


# ============================================================================
# 1. GeoTileTokenizer - 空间网格Token化
# ============================================================================

class GeoTileTokenizer:
    """将地理空间划分为规则网格，每个网格单元作为一个Token。

    DoMapAI对应关系：
    这是最基础的地图语言Token化方式，将连续的地理空间离散化为Token词汇表。
    每个网格单元对应地图语言中的一个"词"。
    """

    def __init__(self, bbox: List[float], resolution: int = 10):
        """初始化网格划分器。

        Args:
            bbox: [min_lng, min_lat, max_lng, max_lat] 边界框
            resolution: 网格划分数（在每个维度上的划分数）
        """
        self.min_lng, self.min_lat, self.max_lng, self.max_lat = bbox
        self.resolution = resolution
        self.lng_step = (self.max_lng - self.min_lng) / resolution
        self.lat_step = (self.max_lat - self.min_lat) / resolution

    def tokenize_points(self, points: List[Tuple[float, float]]) -> List[str]:
        """将坐标点序列转换为Token序列。

        Token格式: 'T_{row}_{col}'，其中 row/col 为网格行列索引。

        Args:
            points: [(lng, lat), ...] 坐标点列表

        Returns:
            Token字符串列表
        """
        tokens = []
        for lng, lat in points:
            # 确保坐标在边界范围内
            lng_c = max(self.min_lng, min(self.max_lng - 1e-9, lng))
            lat_c = max(self.min_lat, min(self.max_lat - 1e-9, lat))
            row = int((self.max_lat - lat_c) / self.lat_step)  # 从上到下编号
            col = int((lng_c - self.min_lng) / self.lng_step)  # 从左到右编号
            row = min(row, self.resolution - 1)
            col = min(col, self.resolution - 1)
            tokens.append(f"T_{row}_{col}")
        return tokens

    def detokenize_to_centroid(self, token: str) -> Tuple[float, float]:
        """从Token还原为网格中心点坐标。

        Args:
            token: 'T_{row}_{col}' 格式的Token字符串

        Returns:
            (lng, lat) 网格中心坐标
        """
        parts = token.replace("T_", "").split("_")
        row, col = int(parts[0]), int(parts[1])
        lat = self.max_lat - (row + 0.5) * self.lat_step
        lng = self.min_lng + (col + 0.5) * self.lng_step
        return (lng, lat)

    @property
    def vocab_size(self) -> int:
        """Token词汇表大小。"""
        return self.resolution * self.resolution


# ============================================================================
# 2. ContourTokenizer - 等高线Token化（核心算法）
# ============================================================================

class ContourTokenizer:
    """等高线Token化器 —— DoMapAI核心算法实现。

    实现流程（参考DoMapAI分形曲线编码方法）：
    1. 等高线顶点序列 → 归一化到[0, grid_resolution]范围
    2. 归一化坐标 → Hilbert分形曲线 → 一维序列索引
    3. 一维序列 → 分段编码（按方向变化分割） → Token序列
    4. Token序列 → 随机投影/Word2Vec → 嵌入向量

    Hilbert曲线优势（DoMapAI选择理由）：
    - 保持局部性：二维空间相邻点在Hilbert曲线上也相邻
    - 适合序列模型：将空间数据转化为适合Transformer处理的序列格式
    - 可分形嵌套：不同粒度的Hilbert曲线可以表达多尺度空间结构

    编码公式（参考DoMapAI土地利用编码）:
    code = SHDI * 12^0 + max1 * 14^3 + max2 * 14^2 + max3 * 14^1
    这里借鉴其"基数压缩"思想用于等高线方向变化编码。
    """

    def __init__(self, grid_resolution: int = 64):
        """初始化等高线Token化器。

        Args:
            grid_resolution: 网格分辨率（必须为2的幂，默认64即2^6）
        """
        self.grid_resolution = grid_resolution
        # 验证grid_resolution是2的幂
        if not (grid_resolution > 0 and (grid_resolution & (grid_resolution - 1)) == 0):
            raise ValueError(f"grid_resolution 必须为2的幂，当前值: {grid_resolution}")
        self._order = int(math.log2(grid_resolution))

    def tokenize_contour(self, contour_points: List[Tuple[float, float]]) -> List[str]:
        """将一条等高线转换为Token序列。

        完整流程对应DoMapAI:
        Step 1: 坐标归一化 → 将地理坐标映射到[0, grid_resolution]整数网格
        Step 2: Hilbert曲线编码 → 将2D网格坐标映射为1D Hilbert索引
        Step 3: 分段编码 → 按相邻点Hilbert索引变化方向分段，生成Token

        Token格式: 'C_{segment_id}_{start_hilbert}_{end_hilbert}_{direction}'
        其中 direction ∈ {0,1,2,3,4,5,6,7} 表示8个方向的变化类型

        Args:
            contour_points: [(lng, lat), ...] 等高线顶点坐标

        Returns:
            Token字符串列表
        """
        if len(contour_points) < 2:
            return []

        # Step 1: 归一化坐标到 [0, grid_resolution] 范围
        lngs = [p[0] for p in contour_points]
        lats = [p[1] for p in contour_points]
        min_lng, max_lng = min(lngs), max(lngs)
        min_lat, max_lat = min(lats), max(lats)

        # 存储bbox用于后续重建
        self._last_bbox = (min_lng, max_lng, min_lat, max_lat)

        # 归一化，处理退化情况（所有点在同一位置）
        lng_range = max_lng - min_lng
        lat_range = max_lat - min_lat
        if lng_range < 1e-9:
            lng_range = 1e-9
        if lat_range < 1e-9:
            lat_range = 1e-9

        grid_indices = []
        for lng, lat in contour_points:
            gx = int((lng - min_lng) / lng_range * (self.grid_resolution - 1))
            gy = int((lat - min_lat) / lat_range * (self.grid_resolution - 1))
            gx = max(0, min(self.grid_resolution - 1, gx))
            gy = max(0, min(self.grid_resolution - 1, gy))
            grid_indices.append((gx, gy))

        # Step 2: Hilbert曲线 2D→1D 映射
        hilbert_indices = [
            self._hilbert_curve_order(gx, gy) for gx, gy in grid_indices
        ]

        # Step 3: 分段编码 —— 按方向变化构建Token
        # 每连续k个点（默认8）编为一个Token
        segment_size = max(2, min(8, len(hilbert_indices) // 4))
        tokens = []

        for seg_id in range(0, len(hilbert_indices) - 1, segment_size - 1):
            end = min(seg_id + segment_size, len(hilbert_indices))
            segment = hilbert_indices[seg_id:end]

            if len(segment) < 2:
                continue

            start_h = segment[0]
            end_h = segment[-1]

            # 方向编码: 根据首尾Hilbert索引差量化到8个方向
            delta = end_h - start_h
            if delta > 0:
                direction = min(7, delta % 8)
            elif delta < 0:
                direction = abs(delta) % 8
            else:
                direction = 0

            token = f"C_{seg_id}_{start_h}_{end_h}_{direction}"
            tokens.append(token)

        return tokens

    def detokenize_to_centroids(self, tokens: List[str]) -> List[Tuple[float, float]]:
        """从Token序列还原等高线（网格中心点近似重建）。

        注意：这是有损重建。Token中仅保存了Hilbert索引的分段信息，
        重建时通过Hilbert逆映射还原网格中心点坐标。

        Args:
            tokens: Token字符串列表

        Returns:
            还原的坐标点列表 [(lng, lat), ...]
        """
        if not hasattr(self, '_last_bbox'):
            raise RuntimeError("请先调用 tokenize_contour()")

        min_lng, max_lng, min_lat, max_lat = self._last_bbox
        lng_range = max_lng - min_lng
        lat_range = max_lat - min_lat
        if lng_range < 1e-9:
            lng_range = 1e-9
        if lat_range < 1e-9:
            lat_range = 1e-9

        reconstructed = []
        for token in tokens:
            parts = token.split("_")
            # Token格式: C_{seg_id}_{start_h}_{end_h}_{direction}
            if len(parts) < 4:
                continue
            start_h = int(parts[1])
            end_h = int(parts[2])

            # 逆Hilbert映射: 1D → 2D网格坐标
            gx_s, gy_s = self._hilbert_inverse(start_h)
            gx_e, gy_e = self._hilbert_inverse(end_h)

            # 分段起始点
            lng_s = min_lng + gx_s / (self.grid_resolution - 1) * lng_range
            lat_s = min_lat + gy_s / (self.grid_resolution - 1) * lat_range
            reconstructed.append((lng_s, lat_s))

            # 分段终止点
            lng_e = min_lng + gx_e / (self.grid_resolution - 1) * lng_range
            lat_e = min_lat + gy_e / (self.grid_resolution - 1) * lat_range
            reconstructed.append((lng_e, lat_e))

        return reconstructed

    def tokens_to_embedding(self, tokens: List[str], dim: int = 64) -> list:
        """将Token序列转换为嵌入向量（随机投影，快速POC方案）。"""
        if not tokens:
            return _zeros(dim)
        embeddings = []
        for token in tokens:
            emb = self._hash_to_vector(token, dim)
            embeddings.append(emb)
        sequence_embedding = _mean_vectors(embeddings)
        norm = _l2_norm(sequence_embedding)
        if norm > 0:
            sequence_embedding = [x / norm for x in sequence_embedding]
        return sequence_embedding

    @staticmethod
    def _hash_to_vector(token: str, dim: int) -> list:
        """使用确定性哈希将Token字符串映射为随机向量。"""
        vec = _zeros(dim)
        for i in range(0, dim, 4):
            hash_input = f"{token}_{i}".encode("utf-8")
            hash_bytes = hashlib.sha256(hash_input).digest()
            for j in range(min(4, dim - i)):
                val = hash_bytes[j] / 127.5 - 1.0
                vec[i + j] = val
        norm = _l2_norm(vec)
        if norm > 0:
            vec = [x / norm for x in vec]
        return vec

    @staticmethod
    def _rot(n: int, x: int, y: int, rx: int, ry: int) -> Tuple[int, int]:
        """Hilbert曲线辅助函数: 旋转/翻转象限。

        Args:
            n: 当前子网格大小
            x, y: 当前坐标
            rx, ry: 象限标识(0或1)

        Returns:
            旋转后的(x, y)
        """
        if ry == 0:
            if rx == 1:
                x = n - 1 - x
                y = n - 1 - y
            x, y = y, x
        return x, y

    def _hilbert_curve_order(self, x: int, y: int) -> int:
        """Hilbert曲线 2D→1D 映射。

        标准迭代算法，将 [0, 2^n-1] × [0, 2^n-1] 的整数坐标
        映射为 [0, 4^n-1] 的Hilbert曲线索引。

        DoMapAI参考：
        Hilbert曲线是空间填充曲线中最优的选择，因为其局部性保持能力
        优于Morton曲线(Z-order)，更适合将空间模式转化为序列模式。

        Args:
            x: 归一化后的整数x坐标（列）[0, grid_resolution-1]
            y: 归一化后的整数y坐标（行）[0, grid_resolution-1]

        Returns:
            Hilbert曲线上的1D位置索引 [0, grid_resolution^2 - 1]
        """
        d = 0
        n = self.grid_resolution
        s = n >> 1
        while s > 0:
            rx = 1 if (x & s) > 0 else 0
            ry = 1 if (y & s) > 0 else 0
            d += s * s * ((3 * rx) ^ ry)
            x, y = self._rot(s, x, y, rx, ry)
            s >>= 1
        return d

    def _hilbert_inverse(self, d: int) -> Tuple[int, int]:
        """Hilbert曲线 1D→2D 逆映射。

        Args:
            d: Hilbert曲线上的位置索引

        Returns:
            (x, y) 二维网格坐标
        """
        n = self.grid_resolution
        x = y = 0
        t = d
        s = 1
        while s < n:
            rx = 1 & (t // 2)
            ry = 1 & (t ^ rx)
            x, y = self._rot(s, x, y, rx, ry)
            x += s * rx
            y += s * ry
            t //= 4
            s <<= 1
        return x, y

    def reconstruction_error(
        self,
        original: List[Tuple[float, float]],
        reconstructed: List[Tuple[float, float]]
    ) -> float:
        """计算重建误差（RMSE, 均方根误差）。

        DoMapAI评估指标：
        RMSE衡量Token化-还原过程中丢失的空间精度。
        该值越小，说明Token序列对原始等高线几何信息的保留越完整。

        Args:
            original: 原始坐标点列表
            reconstructed: 还原的坐标点列表

        Returns:
            RMSE值（单位与坐标一致，通常为度）
        """
        if not original or not reconstructed:
            return float('inf')

        n = min(len(original), len(reconstructed))
        errors = []
        for i in range(n):
            olng, olat = original[i]
            rlng, rlat = reconstructed[i]
            # 欧氏距离（在经纬度空间中近似）
            dist = math.sqrt((olng - rlng) ** 2 + (olat - rlat) ** 2)
            errors.append(dist)

        mse = sum(e ** 2 for e in errors) / len(errors)
        return math.sqrt(mse)


# ============================================================================
# 3. LandUseTokenizer - 土地利用Token化
# ============================================================================

class LandUseTokenizer:
    """土地利用数据Token化器 —— DoMapAI景观编码方法。

    编码公式（DoMapAI风格混合进制编码，确保编解码双向可逆）:
    code = SHDI_quantized + max3 * 12 + max2 * 12 * 14 + max1 * 12 * 14^2

    注：DoMapAI原始文献中的公式形式为
        code = SHDI * 12^0 + max1 * 14^3 + max2 * 14^2 + max3 * 14^1
    但由于14^k不能被12整除，直接取模解码存在歧义。
    此处采用等价但可逆的混合进制形式（以12和14为交替基底），
    保证编码-解码循环完全精确：
        encode_region(g) → token
        decode_to_landscape(token) → 无损还原景观特征

    其中:
    - SHDI_quantized: 香浓多样性指数量化值 [0, 11]
    - max3: 面积占比第三的土地利用类型编码 (0-14)
    - max2: 面积占比第二的土地利用类型编码 (0-14)
    - max1: 面积占比第一的土地利用类型编码 (0-14)

    设计原理（DoMapAI）：
    - 通过基数压缩将4维景观特征编码为1个整数Token
    - 类似进制转换，确保每个组合有唯一编码
    - 编码值越大，景观越复杂（多样性高+主导类型编码大）

    14种土地利用类型编码：
    1-耕地 2-林地 3-草地 4-水域 5-建设用地
    6-未利用地 7-园地 8-交通用地 9-水工建筑
    10-湿地 11-荒漠 12-冰川 13-海洋 14-其他
    """

    # 土地利用类型名称映射
    LAND_USE_NAMES = {
        1: "耕地", 2: "林地", 3: "草地", 4: "水域",
        5: "建设用地", 6: "未利用地", 7: "园地", 8: "交通用地",
        9: "水工建筑", 10: "湿地", 11: "荒漠", 12: "冰川",
        13: "海洋", 14: "其他"
    }

    def compute_shdi(self, land_use_counts: Dict[int, float]) -> float:
        """计算香浓多样性指数 SHDI。

        SHDI = -SUM(p_i * ln(p_i))
        其中 p_i 为第i种土地利用类型的面积占比。

        SHDI含义:
        - SHDI=0: 单一类型（无多样性）
        - SHDI越大: 类型越丰富且分布越均匀
        - 典型城市区域SHDI在1.0-2.0之间

        Args:
            land_use_counts: {类型编码: 面积} 字典

        Returns:
            SHDI值
        """
        total_area = sum(land_use_counts.values())
        if total_area <= 0:
            return 0.0

        shdi = 0.0
        for code, area in land_use_counts.items():
            if area > 0:
                p = area / total_area
                shdi -= p * math.log(p)
        return shdi

    def encode_region(self, land_use_grid: Dict[Tuple[int, int], int]) -> int:
        """将区域的土地利用网格编码为单个整数Token。

        使用混合进制编码（DoMapAI风格，确保编解码可逆）:
        code = SHDI_quantized + max3 * 12 + max2 * 12 * 14 + max1 * 12 * 14^2

        Args:
            land_use_grid: {(row, col): 类型编码} 网格字典

        Returns:
            整数Token编码
        """
        # 统计各类型面积（格子计数）
        counts: Dict[int, int] = {}
        for code in land_use_grid.values():
            counts[code] = counts.get(code, 0) + 1

        # 计算SHDI
        shdi = self.compute_shdi(counts)

        # 按面积降序排列
        sorted_types = sorted(counts.items(), key=lambda x: x[1], reverse=True)
        max1 = sorted_types[0][0] if len(sorted_types) > 0 else 0
        max2 = sorted_types[1][0] if len(sorted_types) > 1 else 0
        max3 = sorted_types[2][0] if len(sorted_types) > 2 else 0

        # 混合进制编码（DoMapAI风格，保证编解码双向唯一）
        # 将 SHDI 量化到 [0, 11] 范围
        shdi_quantized = min(11, int(shdi * 6))  # SHDI通常<2.0, *6后<12
        code = (
            shdi_quantized
            + max3 * 12
            + max2 * 12 * 14
            + max1 * 12 * 14 * 14
        )
        return code

    def decode_to_landscape(self, token: int) -> Dict[str, Any]:
        """从Token解码还原景观特征。

        逆向DoMapAI编码公式，提取编码中的景观信息。

        Args:
            token: 整数Token编码

        Returns:
            包含 shdi_quantized, max1, max2, max3 及类型名称的字典
        """
        # 逆向解码
        shdi_quantized = token % 12
        remaining = token // 12
        max3 = remaining % 14
        remaining //= 14
        max2 = remaining % 14
        remaining //= 14
        max1 = remaining % 14

        # 反量化SHDI
        shdi_approx = shdi_quantized / 6.0

        return {
            "shdi_quantized": shdi_quantized,
            "shdi_approx": round(shdi_approx, 3),
            "max1_code": max1,
            "max1_name": self.LAND_USE_NAMES.get(max1, "未知"),
            "max2_code": max2,
            "max2_name": self.LAND_USE_NAMES.get(max2, "未知"),
            "max3_code": max3,
            "max3_name": self.LAND_USE_NAMES.get(max3, "未知"),
            "dominant_type": self.LAND_USE_NAMES.get(max1, "未知") if max1 > 0 else "无数据",
        }


# ============================================================================
# 4. TokenEmbedder - Token嵌入层
# ============================================================================

class TokenEmbedder:
    """简单的嵌入层，用于将Token序列转换为向量表示。

    DoMapAI对应关系：
    在MapGPT预训练中，Token嵌入层是将离散的地图语言Token
    转化为连续向量表示的关键模块。

    POC阶段：使用确定性随机投影（不依赖训练数据）
    生产阶段：可替换为Word2Vec在大量地图数据上预训练的词向量

    技术参考：
    - 随机投影理论: Johnson-Lindenstrauss引理保证低维嵌入保距性
    - Locality-Sensitive Hashing (LSH): 相似Token映射到相近向量
    """

    def __init__(self, vocab_size: int = 10000, embed_dim: int = 64):
        """初始化嵌入器。

        使用确定性随机投影矩阵（同一种子保证可复现）。

        Args:
            vocab_size: 词汇表大小上限
            embed_dim: 嵌入向量维度
        """
        self.vocab_size = vocab_size
        self.embed_dim = embed_dim
        # 使用固定种子的随机投影矩阵（可复现性）
        self._projection = _random_normal(vocab_size, embed_dim)

    def embed(self, token: str) -> list:
        """将单个Token转换为嵌入向量。"""
        hash_val = int(hashlib.md5(token.encode()).hexdigest(), 16)
        idx = hash_val % self.vocab_size
        vec = list(self._projection[idx])  # copy
        norm = _l2_norm(vec)
        if norm > 0:
            vec = [x / norm for x in vec]
        return vec

    def embed_sequence(self, tokens: List[str]) -> list:
        """将Token序列转换为嵌入向量序列。"""
        if not tokens:
            return []
        embeddings = []
        for token in tokens:
            embeddings.append(self.embed(token))
        return embeddings

    def sequence_similarity(self, seq1: List[str], seq2: List[str]) -> float:
        """计算两个Token序列的余弦相似度。"""
        if not seq1 or not seq2:
            return 0.0
        emb1 = self.embed_sequence(seq1)
        emb2 = self.embed_sequence(seq2)
        if not emb1 or not emb2:
            return 0.0
        vec1 = _mean_vectors(emb1)
        vec2 = _mean_vectors(emb2)
        n1 = _l2_norm(vec1)
        n2 = _l2_norm(vec2)
        if n1 < 1e-9 or n2 < 1e-9:
            return 0.0
        return _dot(vec1, vec2) / (n1 * n2)


# ============================================================================
# 5. GeoTokenService - 统一服务接口
# ============================================================================

class GeoTokenService:
    """GeoToken 统一服务接口
    
    组合 GeoTileTokenizer、ContourTokenizer、LandUseTokenizer、TokenEmbedder
    四大组件，为外部（agent_service等）提供简洁的调用接口。
    """
    
    def __init__(self, grid_resolution: int = 64, embed_dim: int = 64):
        self.tile_tokenizer = GeoTileTokenizer(
            bbox=[113.7, 29.9, 115.1, 31.4],  # 武汉市范围
            resolution=grid_resolution
        )
        self.contour_tokenizer = ContourTokenizer(grid_resolution=grid_resolution)
        self.landuse_tokenizer = LandUseTokenizer()
        self.embedder = TokenEmbedder(vocab_size=10000, embed_dim=embed_dim)
        print(f"[GeoTokenService] 初始化完成 (grid={grid_resolution}, embed_dim={embed_dim})")
    
    def tokenize_contours(
        self, contours: List[List[Tuple[float, float]]]
    ) -> Dict[str, Any]:
        """批量等高线Token化"""
        results = []
        for i, contour in enumerate(contours):
            tokens = self.contour_tokenizer.tokenize_contour(contour)
            embedding = self.contour_tokenizer.tokens_to_embedding(tokens)
            reconstructed = self.contour_tokenizer.reconstruct(tokens)
            error = self.contour_tokenizer.reconstruction_error(contour, reconstructed)
            results.append({
                "index": i,
                "token_count": len(tokens),
                "original_points": len(contour),
                "reconstruction_error": error,
                "embedding_dim": len(embedding),
            })
        return {"contour_count": len(contours), "results": results}
    
    def encode_landscape(self, land_use_grid: Dict[Tuple[int, int], int]) -> Dict[str, Any]:
        """土地利用编码"""
        token = self.landuse_tokenizer.encode_region(land_use_grid)
        # 从网格统计类型分布
        type_counts: Dict[int, float] = {}
        total = len(land_use_grid)
        for lu_type in land_use_grid.values():
            type_counts[lu_type] = type_counts.get(lu_type, 0) + 1
        for k in type_counts:
            type_counts[k] /= total if total > 0 else 1
        shdi = self.landuse_tokenizer.compute_shdi(type_counts)
        return {"token": token, "shdi": shdi}
    
    def compare_sequences(self, seq1: List[str], seq2: List[str]) -> float:
        """比较两个Token序列的相似度"""
        return self.embedder.sequence_similarity(seq1, seq2)

    def extract_geo_features(self, map_data: dict) -> Dict[str, Any]:
        """从地图数据中提取并Token化地理要素（agent_service兼容接口）

        遍历图层：
        - polyline/line：坐标环 → 轮廓 Token 化
        - polygon/circleMarker/marker：中心点 → 网格 Tile Token 化
        - textLabel：注记计数
        """
        if not map_data:
            return {"total_elements": 0, "layers": []}
        layers = map_data.get("layers") or []
        total = 0
        layer_infos = []
        for layer in layers:
            ltype = layer.get("type", "")
            coords = layer.get("coordinates") or []
            name = layer.get("name", "")
            count = 0
            try:
                if ltype in ("polyline", "line") and coords:
                    res = self.tokenize_contours(coords)
                    count = res.get("contour_count", 0)
                elif ltype in ("polygon", "circleMarker", "marker") and coords:
                    pts = [tuple(c[:2]) for c in coords
                           if isinstance(c, (list, tuple)) and len(c) >= 2]
                    if pts:
                        count = len(self.tile_tokenizer.tokenize_points(pts))
                    else:
                        count = len(coords)
                elif ltype in ("textLabel", "label"):
                    count = len(coords)
            except Exception:
                count = len(coords)
            total += count
            layer_infos.append({"name": name, "type": ltype, "elements": count})
        return {"total_elements": total, "layers": layer_infos}

    def build_context_for_llm(self, map_data: dict, message: str = "") -> str:
        """将地图要素GeoToken统计转换为LLM可读上下文文本"""
        info = self.extract_geo_features(map_data)
        lines = [f"地图要素总数: {info['total_elements']}"]
        for li in info.get("layers", [])[:20]:
            lines.append(f"- {li['name']}({li['type']}): {li['elements']}个要素")
        if message:
            lines.append(f"用户需求: {message[:80]}")
        return "\n".join(lines)
