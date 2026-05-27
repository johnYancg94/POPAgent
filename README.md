# POPAgent v1.0.0 — Blender AI Agent

[![Blender](https://img.shields.io/badge/Blender-5.1+-blue.svg)](https://www.blender.org/)
[![Python](https://img.shields.io/badge/Python-3.11+-green.svg)](https://www.python.org/)

POPAgent 是一个内置于 Blender 3D View 侧栏的 AI Agent 插件。它基于 **Function Calling** 机制，让大语言模型能够直接调用 Blender API 来帮你完成场景操作、查询状态、执行工具管线——全程在 Blender 界面内通过聊天完成，无需切换窗口。

---

## 功能一览

### 🤖 AI Agent（核心）
- 在 Blender 3D View 侧栏内通过自然语言对话
- **Function Calling**：LLM 可调用内置 Skill（不是生成 Python 代码来执行，而是注册好的安全工具）
- 自动感知场景上下文（选中对象、模式、场景名称、帧数等）
- 多轮 Tool Call 循环（推理 → 调工具 → 推理 → 最终回答），最长 10 轮
- 支持流式输出 + 工具调用同时进行（DeepSeek / OpenAI）
- 自带死循环检测（相同工具+参数重复 ≥3 次自动中止）

### 🧩 内置 Skill（工具）
| Skill | 功能 | 安全级别 |
|---|---|---|
| `blender.query_scene` | 查询场景概要 / 全量对象列表 | 只读，自动 |
| `blender.list_addons` | 列出已启用的全部插件 | 只读，自动 |
| `blender.viewport_screenshot` | 截取 3D Viewport 截图（base64） | 只读，自动 |
| `blender.select_objects` | 按名称列表或 glob 模式选中/反选对象 | 修改场景，可撤销 |
| `blender.set_active` | 设置活动对象 | 修改场景，可撤销 |
| `dev.run_python` | 执行任意 Python 代码（开发者模式） | ⚠️ 高危险，需确认 |

> 第三方插件可通过 `agent_skills.register()` 注册自己的 Skill 到 POPAgent（见下方「扩展集成」）。

### 🔌 多 LLM 提供商
| Provider | Streaming | Function Calling | 需 API Key |
|---|---|---|---|
| **OpenAI** (GPT-4o, GPT-4o-mini) | ✅ | ✅ | ✅ |
| **DeepSeek** | ✅ (含思维链) | ✅ | ✅ |
| **Anthropic** (Claude) | — | ✅ | ✅ |

可在 Preferences 中即时切换，支持自定义 base URL（兼容私有部署）。

### 📝 对话管理
- 流式渲染（逐词显示回答）
- 自动保存对话历史（可收藏/删除/清空）
- 文本附件（支持从 Blender Text Editor 附加代码上下文）
- 回答内容自动分段渲染（文本 / 列表 / 代码块 + 行号）
- 代码块可直接 **复制到剪贴板 / 插入到 Text Editor 光标 / 新建脚本** / **一键运行**（Full 版）

### 🔊 文本朗读（Text-to-Speech）
- 使用 OpenAI TTS API（Whisper）朗读回答
- 可选多种声线（Alloy / Echo / Fable / Onyx / Nova / Shimmer）
- 支持自动播放

### 🎯 右键上下文帮助
- 在任意 Blender UI 元素上右键 → "Ask POPAgent about this"
- 自动提取该元素的 data path / Python command，解释其作用并给出 bpy 代码示例

### 🔧 代码补全（Text Editor）
- 在 Blender Text Editor 中选中代码 → 右键 → 请求 POPAgent 补全
- 自动用占位符标记补全区域

### 🛡️ 安全机制
| 机制 | 说明 |
|---|---|
| **Skill 安全分级** | 自动（never）/ 首次确认（first）/ 每次确认（always） |
| **场景修改告知** | Skill 元数据标明 `modifies_scene` / `writes_files` / `launches_external_process` |
| **会话信任** | 首次确认后可在当前会话内标记为「信任」，不再弹窗 |
| **死循环检测** | 同一工具+参数连续调用 ≥3 次自动中止 |
| **开发者模式** | `dev.run_python` 仅在 Preferences 开启「开发者模式」后可用，且每次执行都需确认 |
| **撤销支持** | 修改场景的 Skill 执行后自动推送 Ctrl+Z 撤销步骤 |

---

## 快速开始

### 1. 安装
将 `pop_agent` 目录放置到 Blender 的 addons 目录：

```
Windows: %APPDATA%\Blender Foundation\Blender\5.1\scripts\addons\
macOS:   ~/Library/Application Support/Blender/5.1/scripts/addons/
Linux:   ~/.config/blender/5.1/scripts/addons/
```

在 Blender 偏好设置 → Add-ons → 搜索 "POPAgent" → 勾选启用。

### 2. 配置 API Key
启用后，在 **3D View 侧栏 → POPAgent → Preferences（齿轮图标）** 中配置：

1. 选择 LLM 提供商（OpenAI / DeepSeek）
2. 填入对应的 API Key 和 Base URL（如有需要）
3. 点击 **Check Dependencies** 安装 `httpx` 依赖
4. （可选）在 System 中开启 **Stream** 以获得流式输出体验

> 支持自定义 Base URL，可用于连接私有部署的 OpenAI 兼容服务。

### 3. 开始对话
在 3D View 侧栏 → POPAgent 面板：

1. 在输入框输入自然语言指令
2. 点击 ▶ 发送
3. Agent 会自动判断是否需要调用工具，执行后给出回答

**示例对话：**

```
你:   场景里有哪些对象？

Agent: 当前场景有 15 个对象：
       - Suzanne（Mesh）
       - Cube（Mesh）
       - Lamp（Light）
       - Camera（Camera）
       ...（更多）

你:   帮我把所有以 "LOD_" 开头的对象选中

Agent: ✅ 已选中 3 个对象：LOD_0, LOD_1, LOD_2
```

---

## 界面指南

### 面板结构（3D View → 侧栏 → POPAgent）

| 面板 | 说明 |
|---|---|
| **POPAgent** | 模型选择 + 输入框 + ▶ 发送 |
| **Answer** | 显示 AI 回答（文本/列表/代码），流式更新 |
| **Attachments** | 管理上下文附件（可绑定 Text Editor 文本块） |
| **History** | 对话历史管理（收藏/删除/清空） |
| **Skills** | 查看/开关已注册的 Skill，管理会话信任 |
| **Tokens** | Token 用量统计 |
| **Links** | 相关链接 |

### Preferences（偏好设置）

| 区域 | 选项 |
|---|---|
| **API Keys** | OpenAI API Key / Base URL，DeepSeek API Key / Base URL |
| **Read Aloud** | TTS 声线选择（OpenAI / DeepSeek） |
| **Display** | 文字宽度微调 |
| **System** | 依赖管理、流式/一次性回答切换、超时设置、Agent 最大迭代次数、开发者模式 |

---

## Agent 架构说明

```
用户输入
    │
    ▼
CHAT_COMPANION_OT_ask (AsyncModalOperatorMixin)
    │
    ├─ asyncio.gather()
    │   ├─ query_api()        ← LLM 调用 + Tool Call 循环
    │   ├─ print_answering_string()  ← UI 动画
    │   └─ print_waiting_string()    ← UI 动画
    │
query_api() → _agent_query()
    │
    ├─ 选择 Provider (OpenAI / DeepSeek / Anthropic)
    ├─ skill_registry.all_skills() → provider.skills_to_tools()
    ├─ MessageBuilder 构造多轮消息
    │
    └─ 工具调用循环（最多 10 轮）
        ├─ provider.build_request(messages, tools)
        ├─ LLM 返回 → provider.parse_response()
        ├─ 如果有 tool_calls:
        │   ├─ 反死循环检测
        │   ├─ executor.run(tc) → 主线程执行 skill handler
        │   └─ 结果追加到消息历史 → 继续循环
        └─ 如果没有 tool_calls:
            └─ 最终文本回答 → 渲染到 UI → 保存到历史
```

### 项目模块

```
POPAgent/
├── __init__.py                  # 注册入口
├── agent_core/                 # Agent 核心
│   ├── skill_registry.py       # 全局 Skill 注册表
│   ├── executor.py             # Skill 调度器（安全门控）
│   ├── confirm_dialog.py       # 用户确认弹窗 + 会话信任
│   ├── context_builder.py      # 场景上下文摘要生成
│   ├── message_builder.py      # 跨 Provider 消息构建
│   ├── main_thread.py          # 主线程任务队列 + bpy Timer
│   └── reverse_pull.py         # 延迟加载的第三方 Skill 补拉
├── builtin_skills/             # 内置 Skill 实现
│   ├── blender_query.py        # 场景查询 / 截图
│   ├── blender_select.py       # 对象选择 / 设活动
│   └── dev_skills.py           # 开发者模式 (run_python)
├── providers/                  # LLM Provider 抽象层
│   ├── base.py                 # BaseProvider / StreamParser
│   ├── openai_compat.py        # OpenAI / DeepSeek
│   └── anthropic.py            # Anthropic Claude
├── panels/                     # UI 面板
│   ├── panel_prompt.py         # 输入区
│   ├── panel_output.py         # 回答区
│   ├── panel_skills.py         # Skill 管理面板
│   └── ...
├── operators/                  # Blender Operators
│   ├── operator_ask.py         # 核心提问 + Agent 循环
│   ├── operator_skills.py      # Skill 开关 / 信任管理
│   └── ...
├── properties/                 # PropertyGroups + Preferences
├── utils/                      # 异步循环 / 依赖管理 / 工具函数
└── full/                       # Full 版功能（代码执行 / TTS / 界面帮助）
```

---

## 扩展集成

> POPAgent v1.0.0 引入了一套轻量的第三方 Skill 注册系统。

任何 Blender 插件都可以将自己的工具注册为 POPAgent 的 Skill，路径为 `<your_addon>.agent_skills`：

```python
# my_addon/agent_skills/__init__.py

from pop_agent.agent_core import skill_registry

MY_SKILL = {
    "name": "my_addon.do_something",
    "description": "描述这个工具做什么",
    "parameters": {
        "type": "object",
        "properties": {
            "param_name": {
                "type": "string",
                "description": "参数说明",
            }
        },
        "required": ["param_name"],
    },
    "owner": "my_addon",
    "handler": _handler_do_something,  # 主线程可调用的函数
    "metadata": {
        "modifies_scene": False,
        "writes_files": False,
        "launches_external_process": False,
        "undoable": False,
        "requires_confirmation": "never",  # never / first / always
    },
}

def register():
    skill_registry.register_skill(MY_SKILL)

def unregister():
    skill_registry.unregister_namespace("my_addon")
```

注册后，Agent 会自动发现该 Skill 并在适当时调用它。

**默认系统提示词也会自动拼接场景上下文，确保 Agent 有足够的 Situational Awareness 来选择合适的工具。**

---

## 安全风险说明

POPAgent 的 Function Calling 与传统的"LLM 生成 Python 代码 → exec()"不同：

| 传统方式 | POPAgent |
|---|---|
| LLM 输出任意 Python 代码字符串 | LLM 输出结构化的 JSON Tool Call |
| 通过 `exec()` 执行，无限制 | 通过注册的 Handler 执行，受 whitelist 限制 |
| 错误可能损坏场景 | 每次调用都经过 `executor.run()` 安全门控 |
| 无法预览操作后果 | `requires_confirmation` 可在执行前弹窗确认 |

但请注意：
- API Key 由你自行管理，插件以明文存储在 Blender 偏好设置中（建议不要将含 Key 的配置分享给他人）
- 启用「开发者模式」会暴露 `dev.run_python` Skill，该 Skill 可执行任意 Python 代码——请仅在信任的环境中使用

---

## FAQ

**Q: Agent 一直调用同一个工具怎么办？**
A: 内置了死循环检测：同一工具+参数连续调用 ≥3 次会自动中止并返回提示。如果遇到误判，可以在对话中要求 agent「直接告诉我答案，不要调用工具」。

**Q: 为什么 Agent 没有调用任何工具？**
A: 检查 Skills 面板确认工具是否已启用（没有隐藏），以及 `agent_mode_enabled` 偏好是否开启（默认开启）。另外，部分简单问答（如"你好"）不需要工具。

**Q: 支持本地模型吗？**
A: 如果本地模型（如 Ollama / vLLM）提供 OpenAI 兼容的 `/v1/chat/completions` 接口并支持 Function Calling，可以在 Preferences 中设置自定义 Base URL 来使用。

**Q: 点击 "Check Dependencies" 失败？**
A: 按终端提示手动安装：
```
<Blender Python> -m pip install httpx --user
```
Blender Python 路径可在 Preferences → System 中找到。

---

## License

GNU General Public License v2.0 or later — see [LICENSE.txt](LICENSE.txt).

POPAgent enables the use of LLMs from various providers. You must obtain your own API keys from them and therefore comply with their terms and privacy policies. The developer of this addon assumes no responsibility or liability for any misuse or damages resulting from its use.
