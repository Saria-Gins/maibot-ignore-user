# 忽略指定用户（Ignore User）

按 QQ 号忽略指定用户在群聊 / 私聊里的发言。被忽略的消息**不会进入麦麦的处理链**——不写上下文、不进记忆、不触发回复，等于麦麦完全看不见这个人。

> 适用场景：群里某个人总在刷屏、或者你不希望麦麦回应某位群友时，用它精确屏蔽，而不必把整个群关掉。

---

## 特性

- **按 QQ 号过滤**：精确到人，不影响群里其它成员
- **可按群限定**：只在指定群忽略，其它群照常聊天
- **可区分群聊 / 私聊**：`group` / `private` / `all` 三种范围
- **零副作用**：命中后消息直接丢弃，不进上下文、不写记忆、不消耗模型额度
- **可观测**：丢弃时写一条 info 日志，方便确认规则是否生效

---

## 安装

### 方式一：插件市场（推荐）

1. 打开 WebUI → **插件** → **市场**
2. 搜索 `忽略指定用户`
3. 安装后重启麦麦

### 方式二：手动 clone

```bash
cd MaiBot/plugins
git clone https://github.com/Saria-Gins/maibot-ignore-user.git local_dps_ignore_user
```

重启麦麦。

### 环境要求

| 项 | 版本 |
|---|---|
| MaiBot | 1.4.4 ~ 1.4.99 |
| Plugin SDK | 2.20.0 ~ 2.99.99 |

---

## 配置

配置文件：`MaiBot/plugins/local_dps_ignore_user/config.toml`

```toml
[plugin]
enabled = true
config_version = "1.0.0"

[filter]
# 生效范围：group 仅群聊、private 仅私聊、all 两者都生效
scope = "group"

# 要忽略的 QQ 号，可以写多个
user_ids = ["123456789", "987654321"]

# 只在指定的群里忽略；留空表示所有群都生效
group_ids = []

# 丢弃时写 info 日志
log_dropped = true
```

| 字段 | 说明 | 默认 |
|---|---|---|
| `plugin.enabled` | 插件总开关 | `true` |
| `filter.scope` | `group` / `private` / `all` | `group` |
| `filter.user_ids` | 要忽略的 QQ 号列表，留空则不过滤 | `[]` |
| `filter.group_ids` | 限定生效的群号，留空表示所有群 | `[]` |
| `filter.log_dropped` | 丢弃时是否写日志 | `true` |

改完配置会热更新，日志里会出现：

```
忽略用户配置已更新：范围=group，忽略 1 个账号，限定群 0 个
```

---

## 生效效果

启动时日志：

```
忽略用户插件已加载：范围=group，忽略 1 个账号，限定群 0 个
```

命中时日志：

```
已忽略来自 2109872574 的消息（范围=group 群=1038154711）
```

---

## 实现原理

插件挂在宿主的入站钩子上：

```python
@HookHandler("chat.receive.before_process", mode=HookMode.BLOCKING, order=HookOrder.EARLY)
async def handle_before_process(self, message):
    ...
    return {"action": "abort"}
```

`abort` 会让宿主直接丢弃这条消息，后续的上下文拼装、记忆写入、planner 与回复流程都不会执行。

判定顺序：

1. 插件是否启用
2. 发送者 QQ 是否在 `user_ids` 中
3. `scope` 是否匹配当前会话类型
4. 若配置了 `group_ids`，当前群是否在其中

四项都满足才丢弃。

---

## 边界说明

- **只影响麦麦的处理链**：消息在适配器层面已经收到并入库（`mai_messages` 表），但不会进入麦麦的上下文与记忆
- **不建议用它替代黑名单**：它只作用于麦麦，不改变 QQ 群本身的权限
- **不支持按昵称 / 群名片匹配**：昵称会变，QQ 号才是稳定标识

---

## 目录结构

```
.
├── _manifest.json      # manifest v2
├── plugin.py           # 入站钩子与判定逻辑
├── config.py           # 配置模型
├── config.toml         # 配置模板
├── CHANGELOG.md
└── LICENSE
```

---

## 开发

```bash
# 改完代码，重启麦麦即可生效；逻辑自测
python tools/test_ignore_user.py
```

---

## 许可

[MIT](./LICENSE)
