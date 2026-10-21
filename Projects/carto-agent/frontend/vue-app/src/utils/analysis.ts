/**
 * 空间分析工具（浏览器端轻量实现）
 * 提供缓冲区、点面叠加（相交）、最近邻分析所需的几何计算
 */

export type LatLng = [number, number]

/** 球面距离（km，Haversine） */
export function haversineKm(a: LatLng, b: LatLng): number {
  const R = 6371
  const dLat = ((b[0] - a[0]) * Math.PI) / 180
  const dLng = ((b[1] - a[1]) * Math.PI) / 180
  const s =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos((a[0] * Math.PI) / 180) * Math.cos((b[0] * Math.PI) / 180) *
    Math.sin(dLng / 2) * Math.sin(dLng / 2)
  return 2 * R * Math.asin(Math.sqrt(s))
}

/** 点到线段距离（度空间，用于简化等） */
export function pointToSegmentDistance(p: number[], a: number[], b: number[]): number {
  const dx = b[0] - a[0]
  const dy = b[1] - a[1]
  const len2 = dx * dx + dy * dy
  let t = len2 === 0 ? 0 : ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / len2
  t = Math.max(0, Math.min(1, t))
  const projX = a[0] + t * dx
  const projY = a[1] + t * dy
  return Math.sqrt((p[0] - projX) * (p[0] - projX) + (p[1] - projY) * (p[1] - projY))
}

/** 射线法判断点是否在多边形环内（点/环均为 [lat, lng]） */
export function pointInRing(point: LatLng, ring: LatLng[]): boolean {
  let inside = false
  const [lat, lng] = point
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [latI, lngI] = ring[i]
    const [latJ, lngJ] = ring[j]
    if (
      lngI > lng !== lngJ > lng &&
      lat < ((latJ - latI) * (lng - lngI)) / (lngJ - lngI) + latI
    ) {
      inside = !inside
    }
  }
  return inside
}

/** 环质心（平均） */
export function ringCentroid(ring: LatLng[]): LatLng {
  let lat = 0
  let lng = 0
  ring.forEach((p) => {
    lat += p[0]
    lng += p[1]
  })
  const n = Math.max(1, ring.length)
  return [lat / n, lng / n]
}

/** 目标点（距离/方位角） */
export function destinationPoint(center: LatLng, distanceKm: number, bearingDeg: number): LatLng {
  const [lat, lng] = center
  const dLat = distanceKm / 110.574
  const dLng = distanceKm / (111.32 * Math.cos((lat * Math.PI) / 180) || 1)
  const rad = (bearingDeg * Math.PI) / 180
  return [lat + dLat * Math.cos(rad), lng + dLng * Math.sin(rad)]
}

/** 点缓冲区：生成圆形环 */
export function bufferPoint(point: LatLng, distanceKm: number, segments = 36): LatLng[] {
  const ring: LatLng[] = []
  for (let i = 0; i < segments; i++) {
    ring.push(destinationPoint(point, distanceKm, (i * 360) / segments))
  }
  ring.push(ring[0])
  return ring
}

/** 面缓冲区（近似：从质心向外扩张每个顶点） */
export function bufferPolygon(ring: LatLng[], distanceKm: number): LatLng[] {
  if (ring.length < 3) return ring
  const centroid = ringCentroid(ring)
  const closed = ring.length > 0 && ring[0][0] === ring[ring.length - 1][0] && ring[0][1] === ring[ring.length - 1][1]
  const pts = closed ? ring.slice(0, -1) : [...ring]
  const result: LatLng[] = pts.map((p) => {
    const d = haversineKm(centroid, p)
    const factor = d > 0.0001 ? (d + distanceKm) / d : 1 + distanceKm / 0.1
    return [
      centroid[0] + (p[0] - centroid[0]) * factor,
      centroid[1] + (p[1] - centroid[1]) * factor,
    ]
  })
  result.push(result[0])
  return result
}

/** 对图层坐标执行缓冲区：points -> 圆形环；polygons -> 扩张环 */
export function bufferCoordinates(
  coords: any,
  type: string,
  distanceKm: number
): LatLng[][] {
  const rings: LatLng[][] = []
  if (type === 'polygon' || type === 'area') {
    ;(coords || []).forEach((ring: any) => {
      if (Array.isArray(ring) && Array.isArray(ring[0])) {
        rings.push(bufferPolygon(ring as LatLng[], distanceKm))
      }
    })
  } else {
    ;(coords || []).forEach((p: any) => {
      if (Array.isArray(p) && p.length >= 2) {
        rings.push(bufferPoint([p[0], p[1]], distanceKm))
      }
    })
  }
  return rings
}

/** 点面叠加：保留落在目标多边形内的点 */
export function intersectPointPolygon(points: LatLng[], polygons: LatLng[][]): LatLng[] {
  return points.filter((p) => polygons.some((ring) => pointInRing(p, ring)))
}

/** 最近邻：返回每个源点到最近目标点的连线与距离 */
export function nearestPairs(
  sources: LatLng[],
  targets: LatLng[]
): { segment: LatLng[]; distanceKm: number }[] {
  return sources.map((s) => {
    let best: LatLng = targets[0] || s
    let bestD = targets.length ? Infinity : 0
    targets.forEach((t) => {
      const d = haversineKm(s, t)
      if (d < bestD) {
        bestD = d
        best = t
      }
    })
    return { segment: [s, best], distanceKm: bestD }
  })
}

/** 提取图层的坐标点集（所有要素） */
export function layerPoints(coords: any, type: string): LatLng[] {
  const pts: LatLng[] = []
  ;(coords || []).forEach((c: any) => {
    if (Array.isArray(c) && typeof c[0] === 'number' && typeof c[1] === 'number') {
      pts.push([c[0], c[1]])
    } else if (Array.isArray(c) && Array.isArray(c[0])) {
      c.forEach((p: any) => {
        if (Array.isArray(p) && p.length >= 2) pts.push([p[0], p[1]])
      })
    }
  })
  return pts
}

/** 提取图层的多边形环集 */
export function layerRings(coords: any, type: string): LatLng[][] {
  const rings: LatLng[][] = []
  if (type !== 'polygon' && type !== 'area') return rings
  ;(coords || []).forEach((ring: any) => {
    if (Array.isArray(ring) && Array.isArray(ring[0])) {
      rings.push(ring as LatLng[])
    }
  })
  return rings
}
