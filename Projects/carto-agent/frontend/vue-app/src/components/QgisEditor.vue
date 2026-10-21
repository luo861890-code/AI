<template>
  <div class="qgis-editor">
    <!-- 菜单栏 -->
    <div class="qgis-menu-bar">
      <div class="menu-item" v-for="menu in menus" :key="menu.id">
        <span class="menu-label">{{ menu.label }}</span>
        <div class="menu-dropdown" v-if="menu.items">
          <div class="menu-item-child" v-for="item in menu.items" :key="item.id" @click="handleMenuAction(item)">
            <i :class="item.icon" v-if="item.icon"></i>
            <span>{{ item.label }}</span>
            <span class="shortcut" v-if="item.shortcut">{{ item.shortcut }}</span>
          </div>
        </div>
      </div>
      <div class="menu-bar-right">
        <button class="back-btn" @click="goBack">
          <i class="fa-solid fa-arrow-left"></i>
          <span>返回主界面</span>
        </button>
      </div>
    </div>

    <!-- 工具栏 - 动态渲染工具组 -->
    <div class="qgis-toolbar">
      <div 
        class="toolbar-group" 
        v-for="group in activeToolGroups" 
        :key="group.id"
      >
        <span class="toolbar-label">{{ group.label }}</span>
        <div class="toolbar-separator"></div>
        <button 
          class="tool-btn" 
          v-for="tool in group.tools" 
          :key="tool.id"
          :title="tool.title"
          :class="{ active: activeTool === tool.id }"
          @click="handleToolClick(tool)"
        >
          <i :class="tool.icon"></i>
        </button>
      </div>
      
      <!-- 工具组自定义按钮 -->
      <div class="toolbar-group toolbar-customize">
        <div class="toolbar-separator"></div>
        <button 
          class="tool-btn tool-customize-btn" 
          title="自定义工具栏"
          @click="showToolGroupSelector = !showToolGroupSelector"
        >
          <i class="fa-solid fa-sliders"></i>
        </button>
        
        <!-- 工具组选择器下拉菜单 -->
        <div class="tool-group-selector" v-if="showToolGroupSelector">
          <div class="selector-header">
            <i class="fa-solid fa-toolbox"></i>
            <span>工具栏工具组</span>
          </div>
          <div class="selector-hint">勾选要显示的工具组</div>
          <div class="selector-list">
            <div 
              class="selector-item" 
              v-for="group in allToolGroups" 
              :key="group.id"
              @click="toggleToolGroup(group.id)"
            >
              <i 
                :class="activeToolGroupIds.includes(group.id) ? 'fa-solid fa-square-check' : 'fa-regular fa-square'"
              ></i>
              <span>{{ group.label }}</span>
              <span class="tool-count">{{ group.tools.length }}个工具</span>
            </div>
          </div>
          <div class="selector-footer">
            <button class="selector-btn" @click="activeToolGroupIds = allToolGroups.map(g => g.id)">全选</button>
            <button class="selector-btn" @click="activeToolGroupIds = []">清空</button>
            <button class="selector-btn primary" @click="showToolGroupSelector = false">完成</button>
          </div>
        </div>
      </div>
    </div>

    <!-- 主体区域 -->
    <div class="qgis-main">
      <!-- 左侧面板 -->
      <div class="qgis-left-panel">
        <div class="panel-tabs">
          <button 
            class="panel-tab" 
            :class="{ active: leftPanelTab === 'layers' }"
            @click="leftPanelTab = 'layers'"
          >
            <i class="fa-solid fa-layer-group"></i>
            <span>图层</span>
          </button>
          <button 
            class="panel-tab" 
            :class="{ active: leftPanelTab === 'style' }"
            @click="leftPanelTab = 'style'"
          >
            <i class="fa-solid fa-palette"></i>
            <span>样式</span>
          </button>
          <button 
            class="panel-tab" 
            :class="{ active: leftPanelTab === 'history' }"
            @click="leftPanelTab = 'history'"
          >
            <i class="fa-solid fa-clock-rotate-left"></i>
            <span>历史</span>
          </button>
        </div>

        <div class="panel-content">
          <!-- 图层面板 -->
          <div v-show="leftPanelTab === 'layers'" class="layers-panel">
            <div class="panel-toolbar">
              <button class="panel-tool-btn" title="添加图层" @click="addLayerByDialog">
                <i class="fa-solid fa-plus"></i>
              </button>
              <button class="panel-tool-btn" title="移除图层" @click="removeSelectedLayer">
                <i class="fa-solid fa-minus"></i>
              </button>
              <button class="panel-tool-btn" title="上移图层" @click="moveLayer(-1)">
                <i class="fa-solid fa-arrow-up"></i>
              </button>
              <button class="panel-tool-btn" title="下移图层" @click="moveLayer(1)">
                <i class="fa-solid fa-arrow-down"></i>
              </button>
              <div class="panel-tool-separator"></div>
              <button class="panel-tool-btn" title="打开属性表" @click="openAttrTable">
                <i class="fa-solid fa-table"></i>
              </button>
              <button class="panel-tool-btn" title="缩放到图层" @click="zoomToSelectedLayer">
                <i class="fa-solid fa-magnifying-glass"></i>
              </button>
            </div>

            <div class="layer-tree">
              <div v-if="mapStore.sortedLayers.length === 0" class="layer-empty">暂无图层</div>
              <div
                v-for="layer in mapStore.sortedLayers"
                :key="layer.id"
                class="layer-item"
                :class="{ selected: selectedLayer === layer.id }"
                @click="selectedLayer = layer.id"
              >
                <input
                  type="checkbox"
                  :checked="layer.visible"
                  @change="mapStore.toggleLayer(layer.id, ($event.target as HTMLInputElement).checked)"
                  @click.stop
                />
                <span class="layer-icon" :class="layerIconClass(layer.data.type)"></span>
                <span class="layer-name-text">{{ layer.data.name }}</span>
              </div>
            </div>
          </div>

          <!-- 样式面板 -->
          <div v-show="leftPanelTab === 'style'" class="style-panel">
            <div class="style-header">
              <span>图层样式</span>
              <span class="layer-name">{{ selectedLayerName }}</span>
            </div>
            <div class="style-content">
              <div class="style-section">
                <label>渲染方式</label>
                <select class="style-select" v-model="renderMode">
                  <option>单点渲染</option>
                </select>
              </div>
              <div class="style-section">
                <label>填充颜色（面）</label>
                <div class="color-row">
                  <input type="color" :value="styleFill" @input="updateStyle('fillColor', ($event.target as HTMLInputElement).value)" class="color-input" />
                  <span class="color-hex">{{ styleFill }}</span>
                </div>
              </div>
              <div class="style-section">
                <label>颜色（线/边框/点）</label>
                <div class="color-row">
                  <input type="color" :value="styleColor" @input="updateStyle('color', ($event.target as HTMLInputElement).value)" class="color-input" />
                  <span class="color-hex">{{ styleColor }}</span>
                </div>
              </div>
              <div class="style-section">
                <label>线宽</label>
                <input type="range" min="0" max="10" :value="styleWeight" @input="updateStyle('weight', parseInt(($event.target as HTMLInputElement).value))" class="style-slider" />
                <span class="slider-value">{{ styleWeight }}px</span>
              </div>
              <div class="style-section">
                <label>透明度</label>
                <input type="range" min="0" max="100" :value="styleOpacity * 100" @input="updateStyle('opacity', parseInt(($event.target as HTMLInputElement).value) / 100)" class="style-slider" />
                <span class="slider-value">{{ Math.round(styleOpacity * 100) }}%</span>
              </div>
            </div>
          </div>

          <!-- 历史面板 -->
          <div v-show="leftPanelTab === 'history'" class="history-panel">
            <div class="history-list">
              <div class="history-item">
                <i class="fa-solid fa-layer-group history-icon add"></i>
                <div class="history-info">
                  <span class="history-action">当前 {{ mapStore.sortedLayers.length }} 个图层</span>
                  <span class="history-time">图层树为实时数据</span>
                </div>
              </div>
              <div class="history-item">
                <i class="fa-solid fa-pen-to-square history-icon style"></i>
                <div class="history-info">
                  <span class="history-action">
                    未保存修改 {{ editStore.dirtyIds.length }} 个图层
                  </span>
                  <span class="history-time">编辑模式中 Ctrl+Z 撤销 / Ctrl+Y 重做</span>
                </div>
              </div>
              <div class="history-item">
                <i class="fa-solid fa-rotate-left history-icon zoom"></i>
                <div class="history-info">
                  <span class="history-action">
                    撤销栈 {{ totalUndoCount }} 条记录
                  </span>
                  <span class="history-time">在“编辑模式”面板操作</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 中央地图画布 -->
      <div class="qgis-map-canvas">
        <div class="map-container" ref="mapContainerRef">
          <MapCanvas />
        </div>
        
        <!-- 地图悬浮工具 -->
        <div class="map-floating-tools">
          <button class="float-tool" title="全屏" @click="toggleFullscreen">
            <i class="fa-solid fa-expand"></i>
          </button>
          <button class="float-tool" title="刷新图层" @click="refreshMap">
            <i class="fa-solid fa-rotate"></i>
          </button>
        </div>

        <!-- 坐标显示 -->
        <div class="map-coords">
          <span>经度: {{ centerLng }}°</span>
          <span>纬度: {{ centerLat }}°</span>
        </div>
      </div>

      <!-- 右侧面板 -->
      <div class="qgis-right-panel">
        <div class="panel-tabs">
          <button 
            class="panel-tab" 
            :class="{ active: rightPanelTab === 'processing' }"
            @click="rightPanelTab = 'processing'"
          >
            <i class="fa-solid fa-gears"></i>
            <span>处理工具箱</span>
          </button>
          <button 
            class="panel-tab" 
            :class="{ active: rightPanelTab === 'attributes' }"
            @click="rightPanelTab = 'attributes'"
          >
            <i class="fa-solid fa-table-list"></i>
            <span>属性</span>
          </button>
        </div>

        <div class="panel-content">
          <!-- 处理工具箱 -->
          <div v-show="rightPanelTab === 'processing'" class="processing-toolbox">
            <div class="toolbox-search">
              <i class="fa-solid fa-magnifying-glass"></i>
              <input type="text" placeholder="搜索工具..." />
            </div>

            <div class="toolbox-groups">
              <div class="toolbox-group">
                <div class="toolbox-group-header" @click="toggleToolboxGroup('geo')">
                  <i class="fa-solid fa-caret-down"></i>
                  <i class="fa-solid fa-globe group-icon"></i>
                  <span>地理处理</span>
                </div>
                <div class="toolbox-items" v-show="toolboxGroups.geo">
                  <div class="toolbox-item" @click="openAnalysis('buffer')">
                    <i class="fa-solid fa-circle-dot"></i>
                    <span>缓冲区</span>
                  </div>
                  <div class="toolbox-item" @click="openAnalysis('overlay')">
                    <i class="fa-solid fa-layer-group"></i>
                    <span>叠加分析</span>
                  </div>
                  <div class="toolbox-item" @click="openAnalysis('overlay')">
                    <i class="fa-solid fa-scissors"></i>
                    <span>裁剪（点∩面）</span>
                  </div>
                  <div class="toolbox-item" @click="openAnalysis('overlay')">
                    <i class="fa-solid fa-object-group"></i>
                    <span>相交</span>
                  </div>
                  <div class="toolbox-item" @click="openAnalysis('overlay')">
                    <i class="fa-solid fa-shapes"></i>
                    <span>交集</span>
                  </div>
                </div>
              </div>

              <div class="toolbox-group">
                <div class="toolbox-group-header" @click="toggleToolboxGroup('analysis')">
                  <i class="fa-solid fa-caret-right"></i>
                  <i class="fa-solid fa-chart-line group-icon"></i>
                  <span>空间分析</span>
                </div>
                <div class="toolbox-items" v-show="toolboxGroups.analysis">
                  <div class="toolbox-item" @click="openAnalysis('nearest')">
                    <i class="fa-solid fa-ruler"></i>
                    <span>最近邻</span>
                  </div>
                  <div class="toolbox-item" @click="showToast('密度分析：请先生成热力图图层')">
                    <i class="fa-solid fa-chart-area"></i>
                    <span>密度分析</span>
                  </div>
                </div>
              </div>

              <div class="toolbox-group">
                <div class="toolbox-group-header" @click="toggleToolboxGroup('conversion')">
                  <i class="fa-solid fa-caret-right"></i>
                  <i class="fa-solid fa-right-left group-icon"></i>
                  <span>数据转换</span>
                </div>
                <div class="toolbox-items" v-show="toolboxGroups.conversion">
                  <div class="toolbox-item" @click="openExportMenu">
                    <i class="fa-solid fa-file-export"></i>
                    <span>格式转换（导出）</span>
                  </div>
                  <div class="toolbox-item" @click="showToast('投影转换：当前仅 Web Mercator')">
                    <i class="fa-solid fa-earth-asia"></i>
                    <span>投影转换</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- 属性面板 -->
          <div v-show="rightPanelTab === 'attributes'" class="attributes-panel">
            <div class="attr-header">
              <span>要素属性</span>
              <span class="feature-count">{{ selectedLayerName }}</span>
            </div>
            <div class="attr-empty">
              <i class="fa-solid fa-table"></i>
              <p>在“图层”标签选择图层，右键或使用面板工具打开属性表</p>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 底部状态栏 -->
    <div class="qgis-status-bar">
      <div class="status-left">
        <span class="status-item">
          <i class="fa-solid fa-check-circle ok"></i>
          已就绪
        </span>
        <span class="status-item">
          投影: WGS84 / Web Mercator
        </span>
        <span class="status-item">
          {{ mapStore.sortedLayers.length }} 个图层
        </span>
      </div>
      <div class="status-center">
        <span class="status-item">
          比例尺: 1:{{ scale.toLocaleString() }}
        </span>
      </div>
      <div class="status-right">
        <span class="status-item">
          <i class="fa-solid fa-mouse-pointer"></i>
          {{ currentToolLabel }}
        </span>
        <span class="status-item">
          坐标: {{ centerLng }}, {{ centerLat }}
        </span>
      </div>
    </div>

    <!-- Toast 提示 -->
    <div class="qgis-toast" v-if="toastVisible">
      <i class="fa-solid fa-info-circle"></i>
      <span>{{ toastMessage }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import MapCanvas from './MapCanvas.vue'
import { useAppStore } from '@/stores/appStore'
import { useMapStore } from '@/stores/mapStore'
import { useEditStore } from '@/stores/editStore'
import api from '@/services/api'

const appStore = useAppStore()
const mapStore = useMapStore()
const editStore = useEditStore()

// 菜单数据
const menus = [
  {
    id: 'file',
    label: '文件',
    items: [
      { id: 'new', label: '新建工程', icon: 'fa-solid fa-file-circle-plus', shortcut: 'Ctrl+N' },
      { id: 'open', label: '打开工程', icon: 'fa-solid fa-folder-open', shortcut: 'Ctrl+O' },
      { id: 'save', label: '保存工程', icon: 'fa-solid fa-floppy-disk', shortcut: 'Ctrl+S' },
      { id: 'saveas', label: '另存为...', icon: 'fa-solid fa-floppy-disk', shortcut: 'Ctrl+Shift+S' },
      { id: 'sep1', type: 'separator' },
      { id: 'import', label: '导入数据', icon: 'fa-solid fa-file-import' },
      { id: 'export', label: '导出地图', icon: 'fa-solid fa-file-export' },
      { id: 'sep2', type: 'separator' },
      { id: 'print', label: '打印', icon: 'fa-solid fa-print', shortcut: 'Ctrl+P' },
      { id: 'sep3', type: 'separator' },
      { id: 'exit', label: '退出', icon: 'fa-solid fa-right-from-bracket' },
    ]
  },
  {
    id: 'edit',
    label: '编辑',
    items: [
      { id: 'undo', label: '撤销', icon: 'fa-solid fa-rotate-left', shortcut: 'Ctrl+Z' },
      { id: 'redo', label: '重做', icon: 'fa-solid fa-rotate-right', shortcut: 'Ctrl+Y' },
      { id: 'sep1', type: 'separator' },
      { id: 'cut', label: '剪切', icon: 'fa-solid fa-scissors', shortcut: 'Ctrl+X' },
      { id: 'copy', label: '复制', icon: 'fa-regular fa-copy', shortcut: 'Ctrl+C' },
      { id: 'paste', label: '粘贴', icon: 'fa-solid fa-paste', shortcut: 'Ctrl+V' },
      { id: 'sep2', type: 'separator' },
      { id: 'selectAll', label: '全选', icon: 'fa-solid fa-check-double', shortcut: 'Ctrl+A' },
      { id: 'deselect', label: '取消选择', icon: 'fa-solid fa-eraser' },
    ]
  },
  {
    id: 'view',
    label: '视图',
    items: [
      { id: 'zoomIn', label: '放大', icon: 'fa-solid fa-magnifying-glass-plus', shortcut: '+' },
      { id: 'zoomOut', label: '缩小', icon: 'fa-solid fa-magnifying-glass-minus', shortcut: '-' },
      { id: 'zoomFull', label: '缩放到全图', icon: 'fa-solid fa-globe', shortcut: 'Ctrl+0' },
      { id: 'zoomLayer', label: '缩放到图层', icon: 'fa-solid fa-layer-group' },
      { id: 'sep1', type: 'separator' },
      { id: 'pan', label: '平移', icon: 'fa-solid fa-hand', shortcut: 'P' },
      { id: 'sep2', type: 'separator' },
      { id: 'fullscreen', label: '全屏', icon: 'fa-solid fa-expand', shortcut: 'F11' },
    ]
  },
  {
    id: 'layer',
    label: '图层',
    items: [
      { id: 'addVector', label: '添加矢量图层', icon: 'fa-solid fa-draw-polygon' },
      { id: 'addRaster', label: '添加栅格图层', icon: 'fa-solid fa-image' },
      { id: 'addWMS', label: '添加WMS图层', icon: 'fa-solid fa-server' },
      { id: 'sep1', type: 'separator' },
      { id: 'newVector', label: '新建矢量图层', icon: 'fa-solid fa-plus' },
      { id: 'newShapefile', label: '新建Shapefile', icon: 'fa-regular fa-square-plus' },
      { id: 'sep2', type: 'separator' },
      { id: 'attrTable', label: '打开属性表', icon: 'fa-solid fa-table', shortcut: 'F6' },
    ]
  },
  {
    id: 'settings',
    label: '设置',
    items: [
      { id: 'options', label: '选项', icon: 'fa-solid fa-gear' },
      { id: 'projection', label: '投影设置', icon: 'fa-solid fa-earth-asia' },
      { id: 'styles', label: '样式管理器', icon: 'fa-solid fa-palette' },
    ]
  },
  {
    id: 'plugins',
    label: '插件',
    items: [
      { id: 'manage', label: '管理插件', icon: 'fa-solid fa-puzzle-piece' },
      { id: 'install', label: '安装插件', icon: 'fa-solid fa-download' },
    ]
  },
  {
    id: 'help',
    label: '帮助',
    items: [
      { id: 'docs', label: '文档', icon: 'fa-solid fa-book' },
      { id: 'about', label: '关于', icon: 'fa-solid fa-circle-info' },
    ]
  },
]

// 工具组定义
interface ToolItem {
  id: string
  icon: string
  title: string
}

interface ToolGroup {
  id: string
  label: string
  tools: ToolItem[]
}

// 所有可用的工具组
const allToolGroups: ToolGroup[] = [
  {
    id: 'file',
    label: '文件',
    tools: [
      { id: 'new', icon: 'fa-solid fa-file-circle-plus', title: '新建工程' },
      { id: 'open', icon: 'fa-solid fa-folder-open', title: '打开工程' },
      { id: 'save', icon: 'fa-solid fa-floppy-disk', title: '保存工程' },
      { id: 'print', icon: 'fa-solid fa-print', title: '打印' },
    ]
  },
  {
    id: 'edit',
    label: '编辑',
    tools: [
      { id: 'undo', icon: 'fa-solid fa-rotate-left', title: '撤销' },
      { id: 'redo', icon: 'fa-solid fa-rotate-right', title: '重做' },
      { id: 'cut', icon: 'fa-solid fa-scissors', title: '剪切' },
      { id: 'copy', icon: 'fa-regular fa-copy', title: '复制' },
      { id: 'paste', icon: 'fa-solid fa-paste', title: '粘贴' },
    ]
  },
  {
    id: 'navigation',
    label: '导航',
    tools: [
      { id: 'pan', icon: 'fa-solid fa-hand', title: '平移' },
      { id: 'zoomIn', icon: 'fa-solid fa-magnifying-glass-plus', title: '放大' },
      { id: 'zoomOut', icon: 'fa-solid fa-magnifying-glass-minus', title: '缩小' },
      { id: 'zoomFull', icon: 'fa-solid fa-globe', title: '缩放到全图' },
      { id: 'zoomLayer', icon: 'fa-solid fa-layer-group', title: '缩放到图层' },
      { id: 'prevView', icon: 'fa-solid fa-arrow-left', title: '上一视图' },
      { id: 'nextView', icon: 'fa-solid fa-arrow-right', title: '下一视图' },
    ]
  },
  {
    id: 'layer',
    label: '图层',
    tools: [
      { id: 'addVector', icon: 'fa-solid fa-draw-polygon', title: '添加矢量图层' },
      { id: 'addRaster', icon: 'fa-solid fa-image', title: '添加栅格图层' },
      { id: 'addWMS', icon: 'fa-solid fa-server', title: '添加WMS图层' },
      { id: 'newVector', icon: 'fa-solid fa-plus', title: '新建矢量图层' },
      { id: 'newShapefile', icon: 'fa-regular fa-square-plus', title: '新建Shapefile' },
    ]
  },
  {
    id: 'digitizing',
    label: '数字化',
    tools: [
      { id: 'startEdit', icon: 'fa-solid fa-pencil', title: '开始编辑' },
      { id: 'saveEdit', icon: 'fa-solid fa-check', title: '保存编辑' },
      { id: 'stopEdit', icon: 'fa-solid fa-xmark', title: '停止编辑' },
      { id: 'addPoint', icon: 'fa-solid fa-location-dot', title: '添加点要素' },
      { id: 'addLine', icon: 'fa-solid fa-minus', title: '添加线要素' },
      { id: 'addPolygon', icon: 'fa-regular fa-square', title: '添加面要素' },
      { id: 'moveFeature', icon: 'fa-solid fa-arrows-up-down-left-right', title: '移动要素' },
      { id: 'deleteFeature', icon: 'fa-solid fa-trash', title: '删除要素' },
    ]
  },
  {
    id: 'vertex',
    label: '顶点编辑',
    tools: [
      { id: 'nodeTool', icon: 'fa-solid fa-vector-square', title: '节点工具' },
      { id: 'addVertex', icon: 'fa-solid fa-plus', title: '添加节点' },
      { id: 'deleteVertex', icon: 'fa-solid fa-minus', title: '删除节点' },
      { id: 'moveVertex', icon: 'fa-solid fa-arrows-up-down-left-right', title: '移动节点' },
      { id: 'mergeVertex', icon: 'fa-solid fa-object-group', title: '合并节点' },
      { id: 'splitFeature', icon: 'fa-solid fa-scissors', title: '分割要素' },
      { id: 'mergeFeatures', icon: 'fa-solid fa-object-ungroup', title: '合并要素' },
    ]
  },
  {
    id: 'advancedEdit',
    label: '高级编辑',
    tools: [
      { id: 'rotate', icon: 'fa-solid fa-rotate', title: '旋转要素' },
      { id: 'scale', icon: 'fa-solid fa-expand', title: '缩放要素' },
      { id: 'mirror', icon: 'fa-solid fa-arrows-left-right', title: '镜像要素' },
      { id: 'offset', icon: 'fa-solid fa-arrows-turn-right', title: '偏移曲线' },
      { id: 'simplify', icon: 'fa-solid fa-wave-square', title: '简化要素' },
      { id: 'smooth', icon: 'fa-solid fa-wand-magic-sparkles', title: '平滑要素' },
      { id: 'buffer', icon: 'fa-solid fa-circle', title: '缓冲区' },
    ]
  },
  {
    id: 'selection',
    label: '选择',
    tools: [
      { id: 'selectRect', icon: 'fa-regular fa-square', title: '按矩形选择' },
      { id: 'selectPolygon', icon: 'fa-solid fa-draw-polygon', title: '按多边形选择' },
      { id: 'selectFree', icon: 'fa-solid fa-hand-dots', title: '按自由形状选择' },
      { id: 'selectRadius', icon: 'fa-regular fa-circle', title: '按半径选择' },
      { id: 'selectAll', icon: 'fa-solid fa-check-double', title: '全选' },
      { id: 'deselect', icon: 'fa-solid fa-eraser', title: '取消选择' },
    ]
  },
  {
    id: 'measure',
    label: '测量',
    tools: [
      { id: 'measureDistance', icon: 'fa-solid fa-ruler', title: '测量距离' },
      { id: 'measureArea', icon: 'fa-solid fa-ruler-combined', title: '测量面积' },
      { id: 'measureAngle', icon: 'fa-solid fa-angle', title: '测量角度' },
    ]
  },
  {
    id: 'georeferencing',
    label: '校准',
    tools: [
      { id: 'addControlPoint', icon: 'fa-solid fa-thumbtack', title: '添加控制点' },
      { id: 'deleteControlPoint', icon: 'fa-solid fa-xmark', title: '删除控制点' },
      { id: 'georeference', icon: 'fa-solid fa-earth-asia', title: '地理配准' },
      { id: 'transform', icon: 'fa-solid fa-arrows-rotate', title: '几何变换' },
      { id: 'warp', icon: 'fa-solid fa-image', title: '影像校正' },
      { id: 'adjust', icon: 'fa-solid fa-sliders', title: '调整大小' },
    ]
  },
  {
    id: 'spatialAnalysis',
    label: '空间分析',
    tools: [
      { id: 'bufferAnalysis', icon: 'fa-solid fa-circle', title: '缓冲区分析' },
      { id: 'overlay', icon: 'fa-solid fa-layer-group', title: '叠加分析' },
      { id: 'clip', icon: 'fa-solid fa-cut', title: '裁剪' },
      { id: 'union', icon: 'fa-solid fa-object-group', title: '合并' },
      { id: 'intersect', icon: 'fa-solid fa-shapes', title: '相交' },
      { id: 'symDiff', icon: 'fa-solid fa-shuffle', title: '对称差' },
    ]
  },
]

// 当前显示的工具组ID列表
const activeToolGroupIds = ref<string[]>(['file', 'edit', 'navigation', 'layer', 'digitizing', 'selection', 'measure'])

// 工具组选择器显示状态
const showToolGroupSelector = ref(false)

// 切换工具组显示状态
function toggleToolGroup(groupId: string) {
  const index = activeToolGroupIds.value.indexOf(groupId)
  if (index > -1) {
    activeToolGroupIds.value.splice(index, 1)
  } else {
    activeToolGroupIds.value.push(groupId)
  }
}

// 获取当前显示的工具组
const activeToolGroups = computed(() => {
  return allToolGroups.filter(g => activeToolGroupIds.value.includes(g.id))
})

// 状态
const leftPanelTab = ref<'layers' | 'style' | 'history'>('layers')
const rightPanelTab = ref<'processing' | 'attributes'>('processing')
const selectedLayer = ref<string | null>(null)
const activeTool = ref('pan')
const isEditing = ref(false)
const scale = ref(50000)
const toastVisible = ref(false)
const toastMessage = ref('')
const mapContainerRef = ref<HTMLDivElement | null>(null)

// 样式编辑
const renderMode = ref('单点渲染')
const styleFill = ref('#3b82f6')
const styleColor = ref('#1e40af')
const styleWeight = ref(1)
const styleOpacity = ref(1)

const selectedLayerName = computed(() => {
  if (!selectedLayer.value) return '未选择图层'
  return mapStore.layerGroups[selectedLayer.value]?.data.name || '未选择图层'
})

const totalUndoCount = computed(() =>
  Object.values(editStore.undoStack).reduce((s, arr) => s + (arr?.length || 0), 0)
)

const centerLat = computed(() =>
  (mapStore.currentMapData?.center?.[0] ?? 30.5928).toFixed(4)
)

const centerLng = computed(() =>
  (mapStore.currentMapData?.center?.[1] ?? 114.3055).toFixed(4)
)

const toolboxGroups = ref({
  geo: true,
  analysis: false,
  conversion: false,
})

// 计算属性
const currentToolLabel = computed(() => {
  const labels: Record<string, string> = {
    pan: '平移工具',
    zoomIn: '放大工具',
    zoomOut: '缩小工具',
    addPoint: '添加点',
    addLine: '添加线',
    addPolygon: '添加面',
    moveFeature: '移动要素',
    deleteFeature: '删除要素',
    nodeTool: '节点工具',
    selectRect: '矩形选择',
    selectPolygon: '多边形选择',
    selectFree: '自由选择',
    selectRadius: '半径选择',
    measureDistance: '测量距离',
    measureArea: '测量面积',
    measureAngle: '测量角度',
  }
  return labels[activeTool.value] || '未知工具'
})

// 方法
function setActiveTool(tool: string) {
  activeTool.value = tool
  showToast(`切换到${currentToolLabel.value}`)
}

// 处理工具按钮点击
function handleToolClick(tool: ToolItem) {
  if (tool.id === 'startEdit') {
    toggleEditing()
    return
  }

  // 绘制/删除/测量/选择工具 -> 复用主视图的编辑引擎
  const editToolMap: Record<string, string> = {
    addPoint: 'point',
    addLine: 'line',
    addPolygon: 'polygon',
  }
  if (editToolMap[tool.id]) {
    appStore.showEditPanel = true
    editStore.setDrawTool(editToolMap[tool.id] as 'point' | 'line' | 'polygon')
    dispatchMapEvent('map-edit-draw', { tool: editToolMap[tool.id] })
    setActiveTool(tool.id)
    return
  }
  if (tool.id === 'deleteFeature') {
    appStore.showEditPanel = true
    dispatchMapEvent('map-edit-delete')
    setActiveTool(tool.id)
    return
  }
  if (tool.id === 'nodeTool' || tool.id === 'moveFeature' || tool.id === 'moveVertex') {
    appStore.showEditPanel = true
    setActiveTool(tool.id)
    return
  }
  if (tool.id === 'measureDistance') {
    dispatchMapEvent('map-measure-start', { mode: 'distance' })
    setActiveTool(tool.id)
    return
  }
  if (tool.id === 'measureArea') {
    dispatchMapEvent('map-measure-start', { mode: 'area' })
    setActiveTool(tool.id)
    return
  }
  if (tool.id.startsWith('select')) {
    dispatchMapEvent('map-edit-clear-selection')
    setActiveTool(tool.id)
    return
  }

  // 触发地图事件（缩放等）
  const mapEvents: Record<string, string> = {
    'zoomIn': 'map-zoom-in',
    'zoomOut': 'map-zoom-out',
    'zoomFull': 'map-zoom-full',
  }

  if (mapEvents[tool.id]) {
    dispatchMapEvent(mapEvents[tool.id])
  }

  const mapTools = ['pan', 'zoomIn', 'zoomOut', 'zoomFull', 'addPoint', 'addLine', 'addPolygon', 
                    'moveFeature', 'deleteFeature', 'nodeTool', 'addVertex', 'deleteVertex',
                    'moveVertex', 'selectRect', 'selectPolygon', 'selectFree', 'selectRadius',
                    'measureDistance', 'measureArea', 'measureAngle']
  
  if (mapTools.includes(tool.id)) {
    setActiveTool(tool.id)
  } else {
    showToast(tool.title)
  }
}

function toggleEditing() {
  appStore.toggleEditPanel()
  isEditing.value = appStore.showEditPanel
  showToast(isEditing.value ? '编辑模式已开启' : '已退出编辑模式')
}

function toggleToolboxGroup(group: string) {
  toolboxGroups.value[group as keyof typeof toolboxGroups.value] = 
    !toolboxGroups.value[group as keyof typeof toolboxGroups.value]
}

function handleMenuAction(item: any) {
  const actions: Record<string, () => void> = {
    save: () => dispatchMapEvent('map-edit-save'),
    saveas: () => dispatchMapEvent('map-edit-save'),
    export: () => window.dispatchEvent(new CustomEvent('map-open-export')),
    undo: () => dispatchMapEvent('map-edit-undo'),
    redo: () => dispatchMapEvent('map-edit-redo'),
    zoomIn: () => dispatchMapEvent('map-zoom-in'),
    zoomOut: () => dispatchMapEvent('map-zoom-out'),
    zoomFull: () => dispatchMapEvent('map-zoom-full'),
    addLayer: () => addLayerByDialog(),
    import: () => appStore.toggleImportModal(),
    metadata: () => appStore.toggleMetadataModal(),
    params: () => appStore.toggleParamsPanel(),
  }
  const fn = actions[item.id]
  if (fn) fn()
  else showToast(item.label)
}

function showToast(message: string) {
  toastMessage.value = message
  toastVisible.value = true
  setTimeout(() => {
    toastVisible.value = false
  }, 2000)
}

function goBack() {
  appStore.switchToMainView()
}

function dispatchMapEvent(name: string, detail?: any) {
  const el = document.getElementById('map-container')
  if (el) {
    el.dispatchEvent(new CustomEvent(name, detail !== undefined ? { detail } : undefined))
  }
}

async function addLayerByDialog() {
  if (!mapStore.currentMapId) {
    showToast('请先生成地图')
    return
  }
  const name = prompt('输入图层名称（如：医院）')
  if (!name || !name.trim()) return
  const type = prompt('输入图层类型（point / line / polygon）', 'point')
  if (!type || !['point', 'line', 'polygon'].includes(type.trim())) {
    showToast('图层类型仅支持 point / line / polygon')
    return
  }
  try {
    await api.addLayer(mapStore.currentMapId, {
      layer_type: type.trim(),
      name: name.trim(),
    })
    const resp = await api.getMap(mapStore.currentMapId)
    const data = resp.data || resp
    mapStore.setMapData(data)
    dispatchMapEvent('map-apply-data', { data })
    showToast('图层已添加')
  } catch (e: any) {
    showToast('添加图层失败: ' + e.message)
  }
}

async function removeSelectedLayer() {
  const layerId = selectedLayer.value
  if (!layerId || !mapStore.currentMapId) {
    showToast('请先选择图层')
    return
  }
  const known = mapStore.currentMapData?.layers?.some((l) => l.id === layerId)
  mapStore.removeLayer(layerId)
  selectedLayer.value = null
  if (known) {
    try {
      await api.removeLayer(mapStore.currentMapId, layerId)
    } catch {}
  }
  dispatchMapEvent('map-refresh-layers')
}

function moveLayer(dir: number) {
  const layerId = selectedLayer.value
  if (!layerId) {
    showToast('请先选择图层')
    return
  }
  if (dir < 0) mapStore.moveLayerUp(layerId)
  else mapStore.moveLayerDown(layerId)
  dispatchMapEvent('map-refresh-layers')
}

function openAttrTable() {
  if (!selectedLayer.value) {
    showToast('请先选择图层')
    return
  }
  appStore.openAttributeTable(selectedLayer.value)
}

function zoomToSelectedLayer() {
  if (!selectedLayer.value) {
    showToast('请先选择图层')
    return
  }
  dispatchMapEvent('map-zoom-to-layer', { layerId: selectedLayer.value })
}

function updateStyle(key: string, value: any) {
  if (!selectedLayer.value) return
  mapStore.updateLayerStyle(selectedLayer.value, { [key]: value })
  if (key === 'fillColor') styleFill.value = value
  if (key === 'color') styleColor.value = value
  if (key === 'weight') styleWeight.value = value
  if (key === 'opacity') styleOpacity.value = value
  dispatchMapEvent('map-refresh-layers')
}

function layerIconClass(type: string): string {
  if (type === 'polyline' || type === 'line') return 'line-icon'
  if (type === 'polygon' || type === 'area') return 'polygon-icon water-color'
  if (type === 'textLabel' || type === 'label') return 'point-icon label-color'
  return 'point-icon poi-color'
}

function openAnalysis(mode: 'buffer' | 'overlay' | 'nearest') {
  appStore.setAnalysisMode(mode)
}

function toggleFullscreen() {
  const el = document.querySelector('.qgis-editor')
  if (!el) return
  if (!document.fullscreenElement) {
    el.requestFullscreen?.().catch(() => showToast('无法全屏'))
  } else {
    document.exitFullscreen?.()
  }
}

function refreshMap() {
  dispatchMapEvent('map-refresh-layers')
  showToast('图层已刷新')
}

function openExportMenu() {
  window.dispatchEvent(new CustomEvent('map-open-export'))
}

watch(
  selectedLayer,
  (layerId) => {
    const layer = layerId ? mapStore.layerGroups[layerId]?.data : null
    const style = layer?.style || {}
    styleFill.value = style.fillColor || '#3b82f6'
    styleColor.value = style.color || '#1e40af'
    styleWeight.value = style.weight ?? 1
    styleOpacity.value = style.opacity ?? 1
  }
)

onMounted(() => {
  const el = document.getElementById('map-container')
  const handler = (e: Event) => {
    const denom = (e as CustomEvent).detail?.denominator
    if (denom) scale.value = denom
  }
  el?.addEventListener('map-scale-update', handler)
})

onUnmounted(() => {
  const el = document.getElementById('map-container')
  el?.removeEventListener('map-scale-update', () => {})
})
</script>

<style scoped>
.qgis-editor {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #f0f0f0;
  font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
  font-size: 12px;
  color: #2c2c2c;
}

/* 菜单栏 */
.qgis-menu-bar {
  height: 28px;
  background: #fafafa;
  border-bottom: 1px solid #d0d0d0;
  display: flex;
  align-items: center;
  padding: 0 4px;
  gap: 2px;
}

.menu-item {
  position: relative;
  padding: 4px 10px;
  cursor: pointer;
  border-radius: 3px;
  font-size: 12px;
}

.menu-item:hover {
  background: #e8e8e8;
}

.menu-label {
  user-select: none;
}

.menu-dropdown {
  position: absolute;
  top: 100%;
  left: 0;
  min-width: 200px;
  background: #fff;
  border: 1px solid #c0c0c0;
  border-radius: 4px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.15);
  padding: 4px 0;
  z-index: 1000;
  display: none;
}

.menu-item:hover .menu-dropdown {
  display: block;
}

.menu-bar-right {
  margin-left: auto;
  display: flex;
  align-items: center;
  padding-right: 8px;
}

.back-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  border: 1px solid #d0d0d0;
  background: #fff;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
  color: #555;
  transition: all 0.2s;
}

.back-btn:hover {
  background: #0066cc;
  color: #fff;
  border-color: #0066cc;
}

.menu-item-child {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  cursor: pointer;
  white-space: nowrap;
}

.menu-item-child:hover {
  background: #0078d7;
  color: #fff;
}

.menu-item-child i {
  width: 16px;
  text-align: center;
  font-size: 12px;
}

.shortcut {
  margin-left: auto;
  color: #888;
  font-size: 11px;
}

.menu-item-child:hover .shortcut {
  color: rgba(255,255,255,0.8);
}

/* 工具栏 */
.qgis-toolbar {
  height: 36px;
  background: #f5f5f5;
  border-bottom: 1px solid #d0d0d0;
  display: flex;
  align-items: center;
  padding: 0 4px;
  gap: 4px;
}

.qgis-toolbar-second {
  height: 32px;
  background: #f0f0f0;
}

.toolbar-group {
  display: flex;
  align-items: center;
  gap: 2px;
  padding: 0 4px;
}

.toolbar-separator {
  width: 1px;
  height: 20px;
  background: #d0d0d0;
  margin: 0 6px;
}

.toolbar-label {
  font-size: 11px;
  color: #666;
  padding: 0 4px;
  font-weight: 500;
}

.tool-btn {
  width: 28px;
  height: 28px;
  border: 1px solid transparent;
  background: transparent;
  border-radius: 3px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  color: #444;
  transition: all 0.15s;
}

.tool-btn:hover {
  background: #e4f0fb;
  border-color: #a8d5ff;
}

.tool-btn.active {
  background: #c4e0f9;
  border-color: #6cb6ff;
  color: #0066cc;
}

/* 自定义工具栏按钮 */
.toolbar-customize {
  position: relative;
}

.tool-customize-btn {
  background: linear-gradient(135deg, #0ea5e9, #06b6d4) !important;
  color: white !important;
  border-color: transparent !important;
}

.tool-customize-btn:hover {
  background: linear-gradient(135deg, #0284c7, #0891b2) !important;
}

/* 工具组选择器 */
.tool-group-selector {
  position: absolute;
  top: 100%;
  right: 0;
  margin-top: 4px;
  width: 240px;
  background: white;
  border: 1px solid #d0d0d0;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  z-index: 1000;
  overflow: hidden;
}

.selector-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: linear-gradient(135deg, #0ea5e9, #06b6d4);
  color: white;
  font-weight: 600;
  font-size: 14px;
}

.selector-hint {
  padding: 8px 16px;
  font-size: 12px;
  color: #666;
  background: #f8fafc;
  border-bottom: 1px solid #e2e8f0;
}

.selector-list {
  max-height: 300px;
  overflow-y: auto;
  padding: 4px 0;
}

.selector-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 16px;
  cursor: pointer;
  transition: background 0.15s;
  font-size: 13px;
}

.selector-item:hover {
  background: #f0f9ff;
}

.selector-item i {
  color: #0ea5e9;
  font-size: 14px;
}

.selector-item .tool-count {
  margin-left: auto;
  font-size: 11px;
  color: #94a3b8;
}

.selector-footer {
  display: flex;
  gap: 8px;
  padding: 10px 16px;
  background: #f8fafc;
  border-top: 1px solid #e2e8f0;
}

.selector-btn {
  flex: 1;
  padding: 6px 8px;
  border: 1px solid #d0d0d0;
  background: white;
  border-radius: 4px;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.15s;
}

.selector-btn:hover {
  background: #f0f9ff;
  border-color: #0ea5e9;
}

.selector-btn.primary {
  background: linear-gradient(135deg, #0ea5e9, #06b6d4);
  color: white;
  border-color: transparent;
}

.selector-btn.primary:hover {
  background: linear-gradient(135deg, #0284c7, #0891b2);
}

/* 主体区域 */
.qgis-main {
  flex: 1;
  display: flex;
  overflow: hidden;
}

/* 左侧面板 */
.qgis-left-panel {
  width: 260px;
  background: #fff;
  border-right: 1px solid #d0d0d0;
  display: flex;
  flex-direction: column;
}

.panel-tabs {
  display: flex;
  background: #f5f5f5;
  border-bottom: 1px solid #d0d0d0;
}

.panel-tab {
  flex: 1;
  padding: 8px 4px;
  border: none;
  background: transparent;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 3px;
  font-size: 11px;
  color: #666;
  border-bottom: 2px solid transparent;
  transition: all 0.2s;
}

.panel-tab:hover {
  background: #e8e8e8;
}

.panel-tab.active {
  color: #0066cc;
  border-bottom-color: #0066cc;
  background: #fff;
}

.panel-tab i {
  font-size: 14px;
}

.panel-content {
  flex: 1;
  overflow: auto;
}

/* 图层面板 */
.panel-toolbar {
  display: flex;
  align-items: center;
  gap: 2px;
  padding: 6px 8px;
  border-bottom: 1px solid #e8e8e8;
  background: #fafafa;
}

.panel-tool-btn {
  width: 24px;
  height: 24px;
  border: 1px solid transparent;
  background: transparent;
  border-radius: 3px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  color: #555;
}

.panel-tool-btn:hover {
  background: #e4f0fb;
  border-color: #a8d5ff;
}

.panel-tool-separator {
  width: 1px;
  height: 16px;
  background: #d0d0d0;
  margin: 0 4px;
}

.layer-tree {
  padding: 4px 0;
}

.layer-empty {
  padding: 20px;
  text-align: center;
  color: #999;
  font-size: 12px;
}

.layer-name-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.label-color {
  background: #7c3aed;
}

.layer-group-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 8px;
  cursor: pointer;
  font-weight: 500;
  font-size: 12px;
}

.layer-group-header:hover {
  background: #f0f7ff;
}

.group-icon {
  color: #f59e0b;
  font-size: 12px;
}

.layer-items {
  padding-left: 20px;
}

.layer-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 8px;
  cursor: pointer;
  font-size: 12px;
  border-left: 3px solid transparent;
}

.layer-item:hover {
  background: #f0f7ff;
}

.layer-item.selected {
  background: #e4f0fb;
  border-left-color: #0066cc;
}

.layer-icon {
  width: 18px;
  height: 14px;
  border-radius: 2px;
  flex-shrink: 0;
}

.point-icon {
  width: 12px;
  height: 12px;
  border-radius: 50%;
}

.line-icon {
  height: 3px;
  background: #3b82f6;
  border-radius: 2px;
}

.polygon-icon {
  border: 1.5px solid #1e40af;
  background: rgba(59, 130, 246, 0.3);
}

.water-color {
  border-color: #1e40af;
  background: rgba(59, 130, 246, 0.5);
}

.building-color {
  border-color: #92400e;
  background: rgba(217, 119, 6, 0.5);
}

.poi-color {
  background: #dc2626;
}

.osm-icon {
  background: linear-gradient(135deg, #7eb87e 0%, #a8d8a8 100%);
}

.satellite-icon {
  background: linear-gradient(135deg, #4a5568 0%, #718096 100%);
}

/* 样式面板 */
.style-header {
  padding: 10px 12px;
  border-bottom: 1px solid #e8e8e8;
  font-weight: 500;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.layer-name {
  font-size: 11px;
  color: #888;
  font-weight: normal;
}

.style-content {
  padding: 12px;
}

.style-section {
  margin-bottom: 16px;
}

.style-section label {
  display: block;
  margin-bottom: 6px;
  font-size: 12px;
  color: #555;
  font-weight: 500;
}

.style-select {
  width: 100%;
  padding: 6px 8px;
  border: 1px solid #d0d0d0;
  border-radius: 4px;
  font-size: 12px;
  background: #fff;
}

.color-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.color-input {
  width: 40px;
  height: 28px;
  border: 1px solid #d0d0d0;
  border-radius: 4px;
  cursor: pointer;
  padding: 2px;
}

.color-hex {
  font-size: 11px;
  color: #666;
  font-family: monospace;
}

.style-slider {
  width: 100%;
  margin: 4px 0;
}

.slider-value {
  font-size: 11px;
  color: #888;
}

/* 历史面板 */
.history-list {
  padding: 8px;
}

.history-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 8px;
  border-radius: 4px;
  margin-bottom: 4px;
}

.history-item:hover {
  background: #f5f5f5;
}

.history-icon {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  flex-shrink: 0;
}

.history-icon.add {
  background: #dcfce7;
  color: #16a34a;
}

.history-icon.style {
  background: #fef3c7;
  color: #d97706;
}

.history-icon.zoom {
  background: #dbeafe;
  color: #2563eb;
}

.history-info {
  flex: 1;
  min-width: 0;
}

.history-action {
  display: block;
  font-size: 12px;
  color: #333;
  margin-bottom: 2px;
}

.history-time {
  font-size: 11px;
  color: #999;
}

/* 地图画布 */
.qgis-map-canvas {
  flex: 1;
  position: relative;
  background: #fff;
  overflow: hidden;
}

.map-container {
  width: 100%;
  height: 100%;
}

.map-floating-tools {
  position: absolute;
  top: 12px;
  right: 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  z-index: 10;
}

.float-tool {
  width: 32px;
  height: 32px;
  border: 1px solid #d0d0d0;
  background: #fff;
  border-radius: 4px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  color: #555;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.float-tool:hover {
  background: #f0f7ff;
  color: #0066cc;
}

.map-coords {
  position: absolute;
  bottom: 12px;
  left: 12px;
  background: rgba(255,255,255,0.9);
  padding: 4px 10px;
  border-radius: 4px;
  font-size: 11px;
  color: #555;
  display: flex;
  gap: 16px;
  border: 1px solid #e0e0e0;
}

/* 右侧面板 */
.qgis-right-panel {
  width: 280px;
  background: #fff;
  border-left: 1px solid #d0d0d0;
  display: flex;
  flex-direction: column;
}

/* 处理工具箱 */
.toolbox-search {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-bottom: 1px solid #e8e8e8;
}

.toolbox-search i {
  color: #999;
  font-size: 12px;
}

.toolbox-search input {
  flex: 1;
  border: none;
  outline: none;
  font-size: 12px;
  background: transparent;
}

.toolbox-groups {
  padding: 4px 0;
}

.toolbox-group-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  cursor: pointer;
  font-weight: 500;
  font-size: 12px;
  background: #fafafa;
  border-bottom: 1px solid #f0f0f0;
}

.toolbox-group-header:hover {
  background: #f0f7ff;
}

.toolbox-items {
  padding: 4px 0;
}

.toolbox-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px 6px 32px;
  cursor: pointer;
  font-size: 12px;
  color: #444;
}

.toolbox-item:hover {
  background: #e4f0fb;
  color: #0066cc;
}

.toolbox-item i {
  font-size: 12px;
  width: 14px;
  text-align: center;
}

/* 属性面板 */
.attr-header {
  padding: 10px 12px;
  border-bottom: 1px solid #e8e8e8;
  font-weight: 500;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.feature-count {
  font-size: 11px;
  color: #888;
  font-weight: normal;
}

.attr-empty {
  padding: 40px 20px;
  text-align: center;
  color: #999;
}

.attr-empty i {
  font-size: 32px;
  margin-bottom: 12px;
  display: block;
  color: #ccc;
}

.attr-empty p {
  font-size: 12px;
}

/* 状态栏 */
.qgis-status-bar {
  height: 24px;
  background: #f0f0f0;
  border-top: 1px solid #d0d0d0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 12px;
  font-size: 11px;
  color: #666;
}

.status-left,
.status-center,
.status-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.status-item {
  display: flex;
  align-items: center;
  gap: 4px;
}

.status-item .ok {
  color: #22c55e;
}

/* Toast */
.qgis-toast {
  position: fixed;
  bottom: 40px;
  left: 50%;
  transform: translateX(-50%);
  background: rgba(0, 0, 0, 0.8);
  color: #fff;
  padding: 10px 20px;
  border-radius: 6px;
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 8px;
  z-index: 9999;
  animation: fadeIn 0.2s ease;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateX(-50%) translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateX(-50%) translateY(0);
  }
}
</style>
