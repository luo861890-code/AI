/**
 * 前端通用工具函数
 * 提供时间格式化、HTML转义、提示框、防抖、剪贴板、文件下载、坐标验证等
 */

const Utils = {
    /**
     * 格式化时间戳为可读字符串
     * @param {number} timestamp - Unix时间戳（秒）
     * @returns {string} 格式化后的时间，如 "2024-01-15 14:30"
     */
    formatTime(timestamp) {
        if (!timestamp) return "";
        const date = new Date(timestamp * 1000);
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, "0");
        const day = String(date.getDate()).padStart(2, "0");
        const hours = String(date.getHours()).padStart(2, "0");
        const minutes = String(date.getMinutes()).padStart(2, "0");
        return `${year}-${month}-${day} ${hours}:${minutes}`;
    },

    /**
     * HTML转义，防止XSS攻击
     * @param {string} text - 原始文本
     * @returns {string} 转义后的安全文本
     */
    escapeHtml(text) {
        if (text === null || text === undefined) return "";
        const map = {
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&#39;"
        };
        return String(text).replace(/[&<>"']/g, (m) => map[m]);
    },

    /**
     * 显示轻量级提示框
     * @param {string} message - 提示消息
     * @param {string} type - 类型：success / error / warning / info
     * @param {number} duration - 显示时长（毫秒）
     */
    showToast(message, type = "info", duration = 3000) {
        // 移除已有的提示框
        const existing = document.getElementById("toast-container");
        if (existing) existing.remove();

        const container = document.createElement("div");
        container.id = "toast-container";
        container.className = "toast-container";

        const toast = document.createElement("div");
        toast.className = `toast toast-${type}`;

        const iconMap = {
            success: "fa-circle-check",
            error: "fa-circle-xmark",
            warning: "fa-triangle-exclamation",
            info: "fa-circle-info"
        };

        toast.innerHTML = `
            <i class="fa-solid ${iconMap[type] || iconMap.info}"></i>
            <span>${this.escapeHtml(message)}</span>
        `;

        container.appendChild(toast);
        document.body.appendChild(container);

        // 触发动画
        setTimeout(() => toast.classList.add("toast-show"), 10);

        // 自动消失
        setTimeout(() => {
            toast.classList.remove("toast-show");
            setTimeout(() => container.remove(), 300);
        }, duration);
    },

    /**
     * 防抖函数
     * @param {Function} fn - 需要防抖的函数
     * @param {number} delay - 延迟时间（毫秒）
     * @returns {Function} 防抖后的函数
     */
    debounce(fn, delay = 300) {
        let timer = null;
        return function (...args) {
            if (timer) clearTimeout(timer);
            timer = setTimeout(() => fn.apply(this, args), delay);
        };
    },

    /**
     * 复制文本到剪贴板
     * @param {string} text - 要复制的文本
     * @returns {Promise<boolean>} 是否复制成功
     */
    async copyToClipboard(text) {
        try {
            if (navigator.clipboard && window.isSecureContext) {
                await navigator.clipboard.writeText(text);
            } else {
                // 降级方案：使用临时textarea
                const textarea = document.createElement("textarea");
                textarea.value = text;
                textarea.style.position = "fixed";
                textarea.style.left = "-9999px";
                document.body.appendChild(textarea);
                textarea.select();
                document.execCommand("copy");
                document.body.removeChild(textarea);
            }
            this.showToast("已复制到剪贴板", "success", 1500);
            return true;
        } catch (err) {
            this.showToast("复制失败", "error", 1500);
            return false;
        }
    },

    /**
     * 下载文件
     * @param {string} filename - 文件名
     * @param {string|Blob} content - 文件内容
     * @param {string} mimeType - MIME类型
     */
    downloadFile(filename, content, mimeType = "text/plain") {
        const blob = content instanceof Blob ? content : new Blob([content], { type: mimeType });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
    },

    /**
     * 验证地理坐标是否合法
     * @param {number} lat - 纬度 (-90 ~ 90)
     * @param {number} lng - 经度 (-180 ~ 180)
     * @returns {boolean} 是否合法
     */
    isValidCoordinate(lat, lng) {
        const latitude = parseFloat(lat);
        const longitude = parseFloat(lng);
        if (isNaN(latitude) || isNaN(longitude)) return false;
        if (latitude < -90 || latitude > 90) return false;
        if (longitude < -180 || longitude > 180) return false;
        return true;
    },

    /**
     * 格式化JSON字符串（用于显示）
     * @param {object|string} data - JSON对象或字符串
     * @returns {string} 格式化后的JSON字符串
     */
    formatJSON(data) {
        try {
            if (typeof data === "string") {
                return JSON.stringify(JSON.parse(data), null, 2);
            }
            return JSON.stringify(data, null, 2);
        } catch (e) {
            return String(data);
        }
    },

    /**
     * 生成唯一ID
     * @returns {string} 唯一标识符
     */
    generateId() {
        return "id_" + Date.now() + "_" + Math.random().toString(36).substr(2, 9);
    },

    /**
     * 生成会话标题（根据消息内容）
     * @param {string} message - 用户消息内容
     * @returns {string} 截断后的标题
     */
    generateSessionTitle(message) {
        if (!message) return "新会话";
        const title = message.trim().substring(0, 20);
        return title.length < message.trim().length ? title + "..." : title;
    },

    /**
     * 渲染Markdown简单格式（粗体、行内代码、换行）
     * @param {string} text - 原始文本
     * @returns {string} HTML字符串
     */
    renderMarkdown(text) {
        if (!text) return "";
        let html = this.escapeHtml(text);
        // 粗体 **text**
        html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
        // 行内代码 `code`
        html = html.replace(/`(.+?)`/g, "<code>$1</code>");
        // 代码块 ```code```
        html = html.replace(/```([\s\S]+?)```/g, "<pre><code>$1</code></pre>");
        // 换行
        html = html.replace(/\n/g, "<br>");
        return html;
    },

    /**
     * 防止快速重复点击
     * @param {HTMLElement} element - 按钮元素
     * @param {number} cooldown - 冷却时间（毫秒）
     * @returns {boolean} 是否可以执行
     */
    throttle(element, cooldown = 1000) {
        if (element.dataset.throttled === "true") return false;
        element.dataset.throttled = "true";
        setTimeout(() => { delete element.dataset.throttled; }, cooldown);
        return true;
    }
};
