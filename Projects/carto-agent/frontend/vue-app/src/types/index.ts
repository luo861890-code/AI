// ========== 会话类型 ==========
export interface Session {
  session_id: string
  title: string
  created_at?: number
  updated_at?: number
}

// ========== 消息类型 ==========
export interface Message {
  id?: string
  session_id?: string
  role: 'user' | 'assistant'
  content: string
  thinking?: string
  steps?: Step[]
  map_id?: string
  map_summary?: MapSummary | null
  map_data?: MapData | null
  geotoken_info?: GeoTokenInfo | null
  rag_sources?: RagSource[]
  graphrag_entities?: string[]
  knowledge_sources?: KnowledgeSources
  quality?: QualityReport | null
  timestamp?: number
  provider?: string
  model?: string
  created_at?: string
}

export interface Step {
  step_id?: string
  name?: string
  status: 'pending' | 'running' | 'success' | 'failed'
  description?: string
}

// ========== 地图数据类型 ==========
export interface MapData {
  map_id?: string
  name?: string
  map_type?: string
  center?: [number, number]
  zoom?: number
  theme?: string
  layers?: MapLayer[]
  legend?: LegendData
  quality?: QualityReport
  metadata?: Record<string, string>
}

export interface MapSummary {
  name?: string
  map_type?: string
  region?: string
  center?: [number, number]
  zoom?: number
  theme?: string
}

export interface MapLayer {
  id: string
  type: LayerType
  name: string
  group?: string
  coordinates?: any
  data?: any
  features?: MapFeature[]
  properties?: Record<string, any>[]
  style?: LayerStyle
  popup?: string
  radius?: number
  visible?: boolean
  metadata?: Record<string, any>
  _lodVisible?: boolean
}

export interface MapFeature {
  type: string
  coordinates: any
  style?: LayerStyle
  properties?: Record<string, any>
  geometry?: any
}

export type LayerType =
  | 'polyline' | 'line'
  | 'polygon' | 'area'
  | 'circleMarker' | 'marker' | 'point'
  | 'textLabel' | 'label'
  | 'heatmap'
  | 'circle'
  | 'geojson'

export interface LayerStyle {
  color?: string
  borderColor?: string
  fillColor?: string
  weight?: number
  opacity?: number
  fillOpacity?: number
  dashArray?: string | null
  radius?: number
  fontSize?: number
  font?: string
  rotation?: number
  center?: boolean
  icon?: string
  iconClass?: string
  kind?: string
  blur?: number
  maxZoom?: number
  minOpacity?: number
  color_scheme?: string[]
  featureColors?: string[]
  labelsEnabled?: boolean
  labelFontSize?: number
  labelColor?: string
  labelPosition?: string
}

// ========== 知识图谱类型 ==========
export interface KGNode {
  id: string
  name?: string
  label: string
  properties?: Record<string, any>
  connections?: number
  degree?: number
  radius?: number
  x?: number
  y?: number
  fx?: number | null
  fy?: number | null
}

export interface KGLink {
  source: string | KGNode
  target: string | KGNode
  type?: string
  relation_type?: string
  value?: number
}

export interface KGGraphData {
  nodes: KGNode[]
  links: KGLink[]
}

// ========== 知识来源类型 ==========
export interface RagSource {
  title: string
  score?: number
}

export interface KnowledgeSources {
  rag?: RagSource[]
  graphrag?: {
    entities?: string[]
  }
  kg_answer?: string
}

// ========== GeoToken类型 ==========
export interface GeoTokenInfo {
  layer_count: number
  total_elements: number
  total_area_km2?: number
  layer_details?: GeoTokenLayerDetail[]
}

export interface GeoTokenLayerDetail {
  name: string
  type: string
  element_count: number
}

// ========== 图例类型 ==========
export interface LegendData {
  title?: string
  items: LegendItem[]
}

export interface LegendItem {
  label: string
  type?: string
  color?: string
  fillColor?: string
  fillOpacity?: number
  weight?: number
  dashArray?: string
  group?: string
  icon?: string
  iconClass?: string
}

// ========== 质量报告类型 ==========
export interface QualityReport {
  summary: { passed_all?: boolean; failed?: number }
  items: QualityItem[]
  warnings?: string[]
}

export interface QualityItem {
  check: string
  passed: boolean
  count?: number
  message?: string
  positions?: [number, number][]
}

// ========== 路径规划类型 ==========
export interface RouteData {
  coordinates: [number, number][]
  distance: number
  duration: number
  profile?: string
  profile_name?: string
  source?: string
  steps?: RouteStep[]
}

export interface RouteStep {
  instruction: string
  distance: number
}

// ========== LLM设置类型 ==========
export interface LLMProvider {
  id: string
  name: string
  models: string[]
  configured?: boolean
  masked_key?: string
}

export interface LLMProvidersData {
  current?: string
  current_provider?: string
  provider?: string
  current_model?: string
  model?: string
  providers?: LLMProvider[]
  available?: LLMProvider[]
}

// ========== SSE流式回调类型 ==========
export interface StreamCallbacks {
  onThinking?: (text: string) => void
  onChunk?: (chunk: string) => void
  onMap?: (data: MapData) => void
  onSteps?: (steps: Step[]) => void
  onRag?: (sources: RagSource[]) => void
  onGraphrag?: (data: { entities?: string[] }) => void
  onGeotoken?: (info: GeoTokenInfo) => void
  onKnowledgeSources?: (sources: KnowledgeSources) => void
  onDone?: (data: { provider?: string; model?: string }) => void
  onError?: (msg: string) => void
}
