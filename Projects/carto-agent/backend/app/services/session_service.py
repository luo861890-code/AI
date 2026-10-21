"""会话管理服务 - 管理用户对话会话

支持会话的创建、查询、删除和消息管理。
会话数据持久化到JSON文件，同时在内存中缓存以加快访问速度。
持久化采用防抖策略：短时间内多次修改合并为一次磁盘写入，避免高频I/O。
"""
import os
import threading
from typing import List, Optional, Dict, Any

from app.core.config import settings
from app.core.exceptions import SessionError
from app.models.agent_models import Session, SessionMessage, AgentStep
from app.utils.helpers import generate_id, get_timestamp, safe_json_loads, safe_json_dumps, ensure_dir


class SessionService:
    """会话管理服务

    使用内存字典缓存会话数据，同时持久化到JSON文件。
    支持多会话管理，每个会话包含多条对话消息。
    """

    # 防抖写入参数：修改后延迟 2 秒写入，期间的新修改会重置计时器
    _SAVE_DEBOUNCE_SECONDS: float = 2.0

    def __init__(self):
        """初始化会话服务，加载历史会话"""
        # 内存会话存储 {session_id: Session}
        self.sessions: Dict[str, Session] = {}
        # 会话文件路径
        self.sessions_file = os.path.join(settings.data_dir, "sessions.json")

        # 确保数据目录存在
        ensure_dir(os.path.dirname(self.sessions_file))

        # 防抖写入相关
        self._save_timer: Optional[threading.Timer] = None
        self._save_lock = threading.Lock()

        # 加载历史会话
        self._load_sessions()
        print(f"[SessionService] 初始化完成，已加载{len(self.sessions)}个会话")

    def create_session(self, title: str = "新会话") -> Session:
        """创建新会话

        Args:
            title: 会话标题，默认"新会话"

        Returns:
            创建的Session对象
        """
        session = Session(
            session_id=generate_id("session"),
            title=title,
            messages=[],
            created_at=get_timestamp(),
            updated_at=get_timestamp(),
        )
        self.sessions[session.session_id] = session
        self._schedule_save()
        print(f"[SessionService] 创建会话: {session.session_id} ({title})")
        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        """获取会话

        Args:
            session_id: 会话ID

        Returns:
            Session对象；会话不存在时返回None（由调用方决定如何处理）
        """
        return self.sessions.get(session_id)

    def list_sessions(self) -> List[Dict[str, Any]]:
        """列出所有会话

        Returns:
            会话摘要列表（按更新时间倒序），每项包含 session_id, title, message_count, created_at, updated_at
        """
        result = []
        for session in self.sessions.values():
            result.append({
                "session_id": session.session_id,
                "title": session.title,
                "message_count": len(session.messages),
                "created_at": session.created_at,
                "updated_at": session.updated_at,
            })
        # 按更新时间倒序排列
        result.sort(key=lambda x: x["updated_at"], reverse=True)
        return result

    def delete_session(self, session_id: str) -> bool:
        """删除会话

        Args:
            session_id: 会话ID

        Returns:
            删除是否成功
        """
        if session_id in self.sessions:
            del self.sessions[session_id]
            self._schedule_save()
            print(f"[SessionService] 删除会话: {session_id}")
            return True
        print(f"[SessionService] 会话不存在: {session_id}")
        return False

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        map_data: Optional[Any] = None,
        steps: Optional[List[AgentStep]] = None,
        thinking: Optional[str] = None,
    ) -> SessionMessage:
        """向会话添加消息

        Args:
            session_id: 会话ID
            role: 消息角色（user/assistant）
            content: 消息内容
            map_data: 关联的地图数据（可选）
            steps: 智能体执行步骤（可选）
            thinking: 思考过程文本（可选）

        Returns:
            创建的SessionMessage对象

        Raises:
            SessionError: 会话不存在
        """
        session = self.sessions.get(session_id)
        if session is None:
            raise SessionError(f"会话不存在: {session_id}")

        # 轻量化地图引用：只保存 map_id 与少量摘要，完整地图数据由 MapService 按需提供
        map_id = None
        map_summary = None
        if isinstance(map_data, dict):
            map_id = map_data.get("map_id") or map_data.get("id")
            if map_id:
                map_summary = {
                    key: map_data.get(key)
                    for key in ("name", "map_type", "region", "center", "zoom", "theme")
                    if map_data.get(key) is not None
                }
            map_data = None

        message = SessionMessage(
            role=role,
            content=content,
            timestamp=get_timestamp(),
            map_id=map_id,
            map_summary=map_summary,
            map_data=None,
            steps=steps,
            thinking=thinking,
        )
        session.messages.append(message)
        session.updated_at = get_timestamp()

        # 如果是第一条用户消息，自动更新会话标题
        if role == "user" and len(session.messages) == 1:
            from app.utils.helpers import truncate_text
            session.title = truncate_text(content, 20)

        self._schedule_save()
        print(f"[SessionService] 添加消息到会话 {session_id}: role={role}, 内容长度={len(content)}")
        return message

    def build_llm_context(self, session_id: str, max_messages: int = 6) -> List[Dict[str, str]]:
        """从会话历史消息构建LLM上下文

        将会话中的历史消息转换为LLM chat接口所需的messages格式，
        只提取role和content，过滤掉map_data/steps等非文本数据。

        Args:
            session_id: 会话ID
            max_messages: 最多包含的历史消息数量（从最近开始倒数）

        Returns:
            LLM消息列表，格式 [{"role": "user/assistant", "content": "..."}]
        """
        session = self.sessions.get(session_id)
        if session is None:
            return []

        # 取最近max_messages条消息
        recent_messages = session.messages[-max_messages:] if session.messages else []

        context = []
        for msg in recent_messages:
            # 兼容SessionMessage对象和字典两种形式
            content = msg.content if hasattr(msg, 'content') else msg.get('content', '')
            role = msg.role if hasattr(msg, 'role') else msg.get('role', 'user')

            if content and role in ('user', 'assistant'):
                # 截断过长的内容以控制token消耗
                truncated = content[:500] if len(content) > 500 else content
                context.append({"role": role, "content": truncated})

        return context

    def _load_sessions(self):
        """从JSON文件加载历史会话"""
        try:
            if not os.path.exists(self.sessions_file):
                print("[SessionService] 会话文件不存在，跳过加载")
                return

            with open(self.sessions_file, "r", encoding="utf-8") as f:
                content = f.read()

            data = safe_json_loads(content, {})
            if not isinstance(data, dict):
                print("[SessionService] 会话文件格式无效，跳过加载")
                return

            for session_id, session_data in data.items():
                try:
                    # 重建Session对象
                    messages = []
                    for msg_data in session_data.get("messages", []):
                        # 重建AgentStep列表
                        steps = None
                        if msg_data.get("steps"):
                            steps = [
                                AgentStep(**step) if isinstance(step, dict) else step
                                for step in msg_data["steps"]
                            ]
                        message = SessionMessage(
                            role=msg_data.get("role", "user"),
                            content=msg_data.get("content", ""),
                            timestamp=msg_data.get("timestamp", get_timestamp()),
                            map_id=msg_data.get("map_id"),
                            map_summary=msg_data.get("map_summary"),
                            map_data=msg_data.get("map_data"),
                            steps=steps,
                            thinking=msg_data.get("thinking"),
                        )
                        messages.append(message)

                    session = Session(
                        session_id=session_data.get("session_id", session_id),
                        title=session_data.get("title", "新会话"),
                        messages=messages,
                        created_at=session_data.get("created_at", get_timestamp()),
                        updated_at=session_data.get("updated_at", get_timestamp()),
                    )
                    self.sessions[session.session_id] = session
                except Exception as e:
                    print(f"[SessionService] 加载会话 {session_id} 失败: {e}")
                    continue

        except Exception as e:
            print(f"[SessionService] 加载会话文件失败: {e}")

    def _schedule_save(self):
        """防抖调度持久化：延迟 _SAVE_DEBOUNCE_SECONDS 后写入，期间的新调用会重置计时器

        避免高频消息交互时每次都全量序列化写盘，将短时间内的多次修改合并为一次磁盘写入。
        """
        with self._save_lock:
            if self._save_timer is not None:
                self._save_timer.cancel()
            self._save_timer = threading.Timer(
                self._SAVE_DEBOUNCE_SECONDS, self._save_sessions
            )
            self._save_timer.daemon = True
            self._save_timer.start()

    def flush(self):
        """立即将待写入的数据持久化到磁盘（用于服务关闭前的安全落盘）"""
        with self._save_lock:
            if self._save_timer is not None:
                self._save_timer.cancel()
                self._save_timer = None
        self._save_sessions()

    def _save_sessions(self):
        """保存会话到JSON文件"""
        try:
            # 序列化所有会话
            data = {}
            for session_id, session in self.sessions.items():
                # 序列化消息列表
                messages_data = []
                for msg in session.messages:
                    msg_data = {
                        "role": msg.role,
                        "content": msg.content,
                        "timestamp": msg.timestamp,
                        "map_data": msg.map_data,
                        "thinking": msg.thinking,
                    }
                    # 序列化步骤列表
                    if msg.steps:
                        msg_data["steps"] = [
                            step.model_dump() if hasattr(step, "model_dump") else step
                            for step in msg.steps
                        ]
                    messages_data.append(msg_data)

                data[session_id] = {
                    "session_id": session.session_id,
                    "title": session.title,
                    "messages": messages_data,
                    "created_at": session.created_at,
                    "updated_at": session.updated_at,
                }

            # 写入文件
            with open(self.sessions_file, "w", encoding="utf-8") as f:
                f.write(safe_json_dumps(data))

        except Exception as e:
            print(f"[SessionService] 保存会话失败: {e}")
