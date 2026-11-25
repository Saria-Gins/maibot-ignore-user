"""忽略指定用户插件入口。

在消息进入宿主处理链之前判断发送者，命中忽略名单就直接丢弃该消息，
使它不进入麦麦的上下文、记忆与回复流程。

同时把忽略名单单向同步给「智能戳一戳」插件的黑名单，
让被忽略的人连戳一戳也不会触发反应。
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from maibot_sdk import HookHandler, MaiBotPlugin
from maibot_sdk.types import ErrorPolicy, HookMode, HookOrder

from .config import IgnoreUserConfig

HOOK_TIMEOUT_MS = 3000
POKE_SYNC_STATE = "poke_sync.json"


class IgnoreUserPlugin(MaiBotPlugin):
    """按 QQ 号忽略指定用户的发言，并同步到戳一戳插件的黑名单。"""

    config_model = IgnoreUserConfig

    async def on_load(self) -> None:
        cfg = self.config.filter
        if cfg.user_ids:
            self.ctx.logger.info(
                "忽略用户插件已加载：范围=%s，忽略 %d 个账号，限定群 %d 个",
                cfg.scope,
                len(cfg.user_ids),
                len(cfg.group_ids),
            )
        else:
            self.ctx.logger.info("忽略用户插件已加载（忽略名单为空，不做任何过滤）")
        self._sync_poke_blacklist()

    async def on_config_update(
        self, scope: str, config_data: Dict[str, Any], version: str
    ) -> None:
        """配置热更新：重新打印规则并同步戳一戳黑名单。"""

        del scope, config_data, version
        cfg = self.config.filter
        self.ctx.logger.info(
            "忽略用户配置已更新：范围=%s，忽略 %d 个账号，限定群 %d 个",
            cfg.scope,
            len(cfg.user_ids),
            len(cfg.group_ids),
        )
        self._sync_poke_blacklist()

    async def on_unload(self) -> None:
        self.ctx.logger.info("忽略用户插件已卸载")

    def _find_poke_plugin_dir(self) -> Optional[Path]:
        """按 manifest id 在插件目录里找到「智能戳一戳」插件。"""

        target = self.config.link.poke_plugin_id.strip()
        if not target:
            return None
        plugins_root = Path(__file__).resolve().parent.parent
        for candidate in plugins_root.iterdir():
            manifest_path = candidate / "_manifest.json"
            if not manifest_path.is_file():
                continue
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if manifest.get("id") == target:
                return candidate
        return None

    def _state_path(self) -> Path:
        return self.ctx.paths.data_dir / POKE_SYNC_STATE

    def _previous_synced(self) -> List[str]:
        path = self._state_path()
        if not path.is_file():
            return []
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        return [str(item) for item in payload.get("synced", [])]

    def _sync_poke_blacklist(self) -> None:
        """把忽略名单单向写入戳一戳插件的 blacklist，保留用户手填条目。"""

        if not self.config.link.sync_poke_blacklist:
            return
        poke_dir = self._find_poke_plugin_dir()
        if poke_dir is None:
            self.ctx.logger.warning(
                "未找到目标插件 %s，跳过戳一戳联动", self.config.link.poke_plugin_id
            )
            return

        config_path = poke_dir / "config.toml"
        if not config_path.is_file():
            self.ctx.logger.warning("目标插件缺少 config.toml，跳过戳一戳联动")
            return

        ignore_ids = [
            str(item).strip() for item in self.config.filter.user_ids if str(item).strip()
        ]
        previous = self._previous_synced()

        text = config_path.read_text(encoding="utf-8")
        block_start = text.find("[user_control]")
        block = "" if block_start == -1 else text[block_start:]
        match = re.search(r"(?m)^blacklist\s*=\s*\[([^\]]*)\]\s*$", block)
        current = re.findall(r'"([^"]*)"', match.group(1)) if match else []

        manual = [item for item in current if item not in previous]
        merged: List[str] = []
        for item in [*manual, *ignore_ids]:
            if item and item not in merged:
                merged.append(item)

        if match and merged == current:
            self.ctx.logger.info("戳一戳黑名单已是目标状态，无需同步")
            return

        rendered = "blacklist = [" + ", ".join(f'"{item}"' for item in merged) + "]"
        if match:
            start = block_start + match.start()
            end = block_start + match.end()
            text = text[:start] + rendered + text[end:]
        else:
            text = _append_to_user_control(text, rendered)
        config_path.write_text(text, encoding="utf-8", newline="\n")

        state_path = self._state_path()
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(
            json.dumps({"synced": ignore_ids}, ensure_ascii=False, indent=1) + "\n",
            encoding="utf-8",
        )
        self.ctx.logger.info(
            "戳一戳黑名单已同步：忽略名单 %d 个，合并后 %d 个",
            len(ignore_ids),
            len(merged),
        )

    @HookHandler(
        "chat.receive.before_process",
        name="dps_ignore_user",
        description="丢弃来自忽略名单的入站消息，不让它进入麦基处理链",
        mode=HookMode.BLOCKING,
        order=HookOrder.EARLY,
        timeout_ms=HOOK_TIMEOUT_MS,
        error_policy=ErrorPolicy.SKIP,
    )
    async def handle_before_process(
        self,
        message: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Optional[Dict[str, Any]]:
        """命中忽略名单时返回 abort。"""

        del kwargs
        if not self.config.plugin.enabled:
            return None
        if not isinstance(message, dict):
            return None

        cfg = self.config.filter
        if not cfg.user_ids:
            return None

        info = message.get("message_info")
        info = info if isinstance(info, dict) else {}
        group_info = info.get("group_info")
        group_info = group_info if isinstance(group_info, dict) else {}
        user_info = info.get("user_info")
        user_info = user_info if isinstance(user_info, dict) else {}

        user_id = str(user_info.get("user_id") or "").strip()
        group_id = str(group_info.get("group_id") or "").strip()
        if not user_id or user_id not in {str(item).strip() for item in cfg.user_ids}:
            return None

        chat_scope = "group" if group_id else "private"
        if cfg.scope != "all" and cfg.scope != chat_scope:
            return None

        if cfg.group_ids and group_id not in {str(item).strip() for item in cfg.group_ids}:
            return None

        if cfg.log_dropped:
            self.ctx.logger.info(
                "已忽略来自 %s 的消息（范围=%s 群=%s）", user_id, chat_scope, group_id or "-"
            )
        return {"action": "abort"}


def _user_control_block(text: str) -> str:
    """取 [user_control] 小节文本，供黑名单定位使用。"""

    start = text.find("[user_control]")
    return "" if start == -1 else text[start:]


def _append_to_user_control(text: str, rendered: str) -> str:
    """小节里没有 blacklist 行时补一行。"""

    start = text.find("[user_control]")
    if start == -1:
        return text.rstrip("\n") + f"\n\n[user_control]\n{rendered}\n"
    line_end = text.find("\n", start)
    if line_end == -1:
        return text + "\n" + rendered + "\n"
    return text[: line_end + 1] + rendered + "\n" + text[line_end + 1:]


def create_plugin() -> MaiBotPlugin:
    return IgnoreUserPlugin()
