"""忽略指定用户的配置模型。"""

from __future__ import annotations

from typing import List, Literal

from maibot_sdk import Field, PluginConfigBase


class PluginSection(PluginConfigBase):
    """插件开关与配置版本。"""

    enabled: bool = Field(default=True, description="是否启用本插件")
    config_version: str = Field(default="1.1.0", description="配置模板版本号")


class FilterSection(PluginConfigBase):
    """忽略规则。"""

    scope: Literal["group", "private", "all"] = Field(
        default="group", description="生效范围：group 仅群聊、private 仅私聊、all 两者都生效"
    )
    user_ids: List[str] = Field(default_factory=list, description="要忽略的 QQ 号")
    group_ids: List[str] = Field(
        default_factory=list, description="仅在這些群里生效；留空表示所有群"
    )
    log_dropped: bool = Field(default=True, description="丢弃消息时写一条 info 日志")


class LinkSection(PluginConfigBase):
    """与其他插件的单向联动。"""

    sync_poke_blacklist: bool = Field(
        default=True, description="把忽略名单单向同步到「智能戳一戳」插件的黑名单"
    )
    poke_plugin_id: str = Field(
        default="TAIY2020.smart_poke_plugin", description="目标插件 ID"
    )


class IgnoreUserConfig(PluginConfigBase):
    """配置根节点。"""

    plugin: PluginSection = Field(default_factory=PluginSection)
    filter: FilterSection = Field(default_factory=FilterSection)
    link: LinkSection = Field(default_factory=LinkSection)
