import { CONFIG } from '@/config'
import type { StreamCallbacks, MapLayer } from '@/types'

class ApiService {
  private baseUrl: string

  constructor() {
    this.baseUrl = CONFIG.apiBaseUrl
  }

  private async request<T = any>(
    method: string,
    url: string,
    data?: Record<string, any> | null
  ): Promise<T> {
    const fullUrl = this.baseUrl + url
    const options: RequestInit = {
      method,
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      credentials: 'omit' as RequestCredentials,
    }

    if (method === 'GET' && data) {
      const params = new URLSearchParams(data as Record<string, string>).toString()
      const separator = fullUrl.includes('?') ? '&' : '?'
      const fetchUrl = fullUrl + separator + params
      const controller = new AbortController()
      const timeoutId = setTimeout(() => controller.abort(), CONFIG.requestTimeout)
      try {
        const response = await fetch(fetchUrl, { ...options, signal: controller.signal })
        clearTimeout(timeoutId)
        if (!response.ok) {
          const errorText = await response.text()
          let errorMsg: string
          try {
            const errorJson = JSON.parse(errorText)
            errorMsg = errorJson.detail || errorJson.message || `请求失败 (${response.status})`
          } catch {
            errorMsg = `请求失败 (${response.status}): ${errorText.substring(0, 200)}`
          }
          throw new Error(errorMsg)
        }
        return await response.json()
      } catch (error: any) {
        clearTimeout(timeoutId)
        if (error.name === 'AbortError') {
          throw new Error('请求超时，请检查网络连接')
        }
        throw error
      }
    } else if (data) {
      options.body = JSON.stringify(data)
    }

    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), CONFIG.requestTimeout)
    try {
      const response = await fetch(fullUrl, { ...options, signal: controller.signal })
      clearTimeout(timeoutId)
      if (!response.ok) {
        const errorText = await response.text()
        let errorMsg: string
        try {
          const errorJson = JSON.parse(errorText)
          errorMsg = errorJson.detail || errorJson.message || `请求失败 (${response.status})`
        } catch {
          errorMsg = `请求失败 (${response.status}): ${errorText.substring(0, 200)}`
        }
        throw new Error(errorMsg)
      }
      return await response.json()
    } catch (error: any) {
      clearTimeout(timeoutId)
      if (error.name === 'AbortError') {
        throw new Error('请求超时，请检查网络连接')
      }
      throw error
    }
  }

  // ========== 会话管理 ==========
  async createSession(title = '新会话') {
    return this.request('POST', '/api/chat/sessions', { title })
  }

  async listSessions() {
    return this.request('GET', '/api/chat/sessions')
  }

  async getSession(sessionId: string) {
    return this.request('GET', `/api/chat/sessions/${sessionId}`)
  }

  async getMessages(sessionId: string) {
    return this.request('GET', `/api/chat/sessions/${sessionId}/messages`)
  }

  async deleteSession(sessionId: string) {
    return this.request('DELETE', `/api/chat/sessions/${sessionId}`)
  }

  async sendMessage(sessionId: string, message: string) {
    return this.request('POST', `/api/chat/sessions/${sessionId}/messages`, { message })
  }

  async streamMessage(sessionId: string, message: string, callbacks: StreamCallbacks) {
    const fullUrl = this.baseUrl + `/api/chat/sessions/${sessionId}/stream`
    const response = await fetch(fullUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'text/event-stream',
      },
      body: JSON.stringify({ message }),
    })

    if (!response.ok) {
      const errText = await response.text()
      throw new Error(`流式请求失败 (${response.status}): ${errText.substring(0, 200)}`)
    }

    const reader = response.body!.getReader()
    const decoder = new TextDecoder('utf-8')
    let buffer = ''

    try {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const events = buffer.split('\n\n')
        buffer = events.pop()!

        for (const eventStr of events) {
          const line = eventStr.trim()
          if (!line.startsWith('data:')) continue
          const jsonStr = line.substring(5).trim()
          if (!jsonStr) continue

          try {
            const data = JSON.parse(jsonStr)
            switch (data.type) {
              case 'thinking':
                callbacks.onThinking?.(data.content || '')
                break
              case 'chunk':
                callbacks.onChunk?.(data.content || '')
                break
              case 'map':
                callbacks.onMap?.(data.content)
                break
              case 'steps':
                callbacks.onSteps?.(data.content || [])
                break
              case 'rag':
                callbacks.onRag?.(data.content || [])
                break
              case 'graphrag':
                callbacks.onGraphrag?.(data.content || {})
                break
              case 'geotoken':
                callbacks.onGeotoken?.(data.content || {})
                break
              case 'knowledge_sources':
                callbacks.onKnowledgeSources?.(data.content || {})
                break
              case 'done':
                callbacks.onDone?.(data)
                break
              case 'error':
                callbacks.onError?.(data.content || '未知错误')
                break
            }
          } catch {
            console.warn('SSE事件解析失败:', jsonStr.substring(0, 100))
          }
        }
      }
    } finally {
      reader.releaseLock()
    }
  }

  // ========== 地图管理 ==========
  async generateMap(params: Record<string, any>) {
    return this.request('POST', '/api/maps/generate', params)
  }

  async listMaps() {
    return this.request('GET', '/api/maps')
  }

  async getMap(mapId: string) {
    return this.request('GET', `/api/maps/${mapId}`)
  }

  async deleteMap(mapId: string) {
    return this.request('DELETE', `/api/maps/${mapId}`)
  }

  async addLayer(mapId: string, params: Record<string, any>) {
    return this.request('POST', `/api/maps/${mapId}/layers`, params)
  }

  async removeLayer(mapId: string, layerId: string) {
    return this.request('DELETE', `/api/maps/${mapId}/layers/${layerId}`)
  }

  async updateLayerStyle(mapId: string, layerId: string, style: Record<string, any>) {
    return this.request('PUT', `/api/maps/${mapId}/layers/${layerId}`, style)
  }

  async setLayerVisible(mapId: string, layerId: string, visible: boolean) {
    return this.request('PUT', `/api/maps/${mapId}/layers/${layerId}/visible`, { visible })
  }

  async updateLayerGeometry(mapId: string, layerId: string, payload: Record<string, any>) {
    return this.request('PUT', `/api/maps/${mapId}/layers/${layerId}/geometry`, payload)
  }

  async patchLayer(mapId: string, layerId: string, patches: Record<string, any>) {
    return this.request('PATCH', `/api/maps/${mapId}/layers/${layerId}`, patches)
  }

  async updateView(mapId: string, params: Record<string, any>) {
    return this.request('PUT', `/api/maps/${mapId}/view`, params)
  }

  async updateTheme(mapId: string, theme: string) {
    return this.request('PUT', `/api/maps/${mapId}/theme`, { theme })
  }

  async modifyMap(mapId: string, instruction: string) {
    return this.request('POST', `/api/maps/${mapId}/modify`, { instruction })
  }

  async exportMap(mapId: string, format: string) {
    return this.request('POST', `/api/maps/${mapId}/export`, { format })
  }

  async getMapQuality(mapId: string) {
    return this.request('GET', `/api/maps/${mapId}/quality`)
  }

  async addMarker(mapId: string, params: Record<string, any>) {
    return this.request('POST', `/api/maps/${mapId}/marker`, params)
  }

  async planRoute(mapId: string, params: Record<string, any>) {
    return this.request('POST', `/api/maps/${mapId}/route`, params)
  }

  // ========== 知识图谱 ==========
  async getKGGraph(limit = 100) {
    return this.request('GET', `/api/kg/graph?limit=${limit}`)
  }

  async kgQuery(question: string) {
    return this.request('POST', '/api/kg/query', { question })
  }

  async importDocument(content: string, entityLabels?: string[] | null) {
    const params: Record<string, any> = { content }
    if (entityLabels) params.entity_labels = entityLabels
    return this.request('POST', '/api/kg/import', params)
  }

  async initKnowledge() {
    return this.request('POST', '/api/kg/init')
  }

  // ========== 系统设置 ==========
  async getProviders() {
    return this.request('GET', '/api/settings/llm/providers')
  }

  async switchProvider(provider: string, model: string) {
    return this.request('PUT', '/api/settings/llm/provider', { provider, model })
  }

  async updateApiKey(provider: string, apiKey: string) {
    return this.request('PUT', '/api/settings/llm/apikey', { provider, api_key: apiKey })
  }

  async getThemes() {
    return this.request('GET', '/api/settings/map/themes')
  }
}

const api = new ApiService()

export default api
