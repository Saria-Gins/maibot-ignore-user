"""忽略指定用户插件入口。

在消息进入宿主处理链之前判断发送者，命中忽略名单就直接丢弃该消息，
使它不进入麦麦的上下文、记忆与回复流程。
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from maibot_sdk import HookHandler, MaiBotPlugin
from maibot_sdk.types import ErrorPolicy, HookMode, HookOrder

from .config import IgnoreUserConfig

HOOK_TIMEOUT_MS = 3000


class IgnoreUserPlugin(MaiBotPlugin):
    """按 QQ 号忽略指定用户的发言。"""

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

    async def on_config_update(
        self, scope: str, config_data: Dict[str, Any], version: str
    ) -> None:
        """配置热更新：重新打印一次生效规则。"""

        del scope, config_data, version
        cfg = self.config.filter
        self.ctx.logger.info(
            "忽略用户配置已更新：范围=%s，忽略 %d 个账号，限定群 %d 个",
            cfg.scope,
            len(cfg.user_ids),
            len(cfg.group_ids),
        )

    async def on_unload(self) -> None:
        self.ctx.logger.info("忽略用户插件已卸载")

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


def create_plugin() -> MaiBotPlugin:
    return IgnoreUserPlugin()
