# POPAgent v1.3.1 — Blender AI Agent

[![Blender](https://img.shields.io/badge/Blender-5.1+-blue.svg)](https://www.blender.org/)
[![Python](https://img.shields.io/badge/Python-3.11+-green.svg)](https://www.python.org/)

POPAgent 是一个内置于 Blender 3D View 侧栏的 AI Agent 插件。它基于 **Function Calling** 机制，让大语言模型能够直接调用 Blender API 来帮你完成场景操作、查询状态、执行工具管线——全程在 Blender 界面内通过聊天完成，无需切换窗口。

---

## 更新日志

### v1.3.1
- 修复 RenderSet Agent 在原生 inspect 成功后最终模型响应卡住时无法给出可追踪结果的问题。
- Agent 现在会从已完成的 RenderSet inspect 结果生成安全 fallback 回答，并保留可继续恢复的中断上下文。
- 执行追踪为 RenderSet 工具保留 bounded 结果字段，便于最终回答和发布 gate 校验。

### v1.3.0
- Answer 面板拆分 Agent 执行过程与最终回答，完成后默认折叠过程摘要。
- Preferences 改为按 Models / Agent / Skills / Interface / Logs / System 分页显示，并新增“默认权限 / 自动权限”快捷切换。
- 首页新增“准备渲染”提示词按钮，快速启动 RenderSet Pro 场景 Context 准备流程。
- 优化 ask_human 选项确认弹窗，完整展示候选回答并保留自由输入。
- RenderSet 工作流补充输出校验与回滚报告约束，减少错误 Context 进入 Render All。

---

## 功能一览

### 🤖 AI Agent（核心）
- 在 Blender 3D View 侧栏内通过自然语言对话
- **Function Calling**：LLM 可调用内置 Skill（不是生成 Python 代码来执行，而是注册好的安全工具）
- 自动感知场景上下文（选中对象、模式、场景名称、帧数等）
- 可选多模态输入：开启后可随 Prompt 发送图片附件（剪贴板粘贴 / 文件 / Blender Image datablock）
- 多轮 Tool Call 循环（推理 → 调工具 → 推理 → 最终回答），最长 15 轮（根据 prompt 复杂度动态调整）
- 支持流式输出 + 工具调用同时进行（DeepSeek / OpenAI / Mimo）
- **智能死循环检测**：归一化工具签名，相同工具+参数重复 ≥3 次自动中止
- **执行追踪**：每轮对话记录延迟、finish_reason、文本预览、工具调用耗时/成败，渲染到回答面板
- **Agent 策略控制**：Preferences 中可配置最大迭代次数和模型超时时间
- **结构化超时**：httpx.Timeout(connect=5s, read=600s)，防止模型思考期间误超时

### 📊 用量记录与挖掘（v1.2.2 新增）
- **自动 JSONL 日志**：每次对话自动写入 `usage_logs/` 目录，按日期 + 会话 ID 组织
- **一键导出 Zip**：`Export Usage Logs` 一键打包本周期日志为 zip（含结构化 `report.txt` + 原始 episodes），导出后自动归档清空
- **用量成本追踪**：Token 用量面板实时统计，支持人民币格式化（按各模型官方定价）
- **Provider 连通性测试**：Preferences 中一键检测 API 连通性

### 🧩 内置 Skill（工具）— 共 33 个

#### 场景查询 & 截图
| Skill | 功能 | 安全级别 |
|---|---|---|
| `blender.query_scene` | 查询场景概要 / 全量对象列表 | 只读，自动 |
| `blender.list_addons` | 列出已启用的全部插件 | 只读，自动 |
| `blender.viewport_screenshot` | 截取 3D Viewport 截图；多模态模型可阅读 | 只读，自动 |
| `blender.api_search` | 搜索 Blender Python API 文档 | 只读，自动 |
| `web.search` | 使用 Tavily 搜索外部网页与最新信息 | 只读，自动 |

#### 选择 & 活动对象
| Skill | 功能 | 安全级别 |
|---|---|---|
| `blender.select_objects` | 按名称列表或 glob 模式选中/反选对象 | 修改场景，可撤销 |
| `blender.set_active` | 设置活动对象 | 修改场景，可撤销 |

#### 材质节点编辑（v1.2.1 新增）
| Skill | 功能 |
|---|---|
| `blender.nodes.search_types` | 按名称/关键词搜索注册的节点类型 |
| `blender.material.inspect_nodes` | 快照所有材质的节点树（节点/连线/图片） |
| `blender.material.validate_nodes` | 对材质运行 PBR 诊断：Principled BSDF 连接、颜色空间、贴图连通性 |
| `blender.material.connect_pbr_textures` | 按名称匹配自动将 PBR 贴图连到 Principled BSDF 正确输入 |
| `blender.material.add_node` | 在材质节点树中添加节点 |
| `blender.material.connect_nodes` | 连接两个材质节点插口 |
| `blender.material.set_node_input` | 设置材质节点输入的默认值 |

#### 几何节点编辑（v1.2.1 新增）
| Skill | 功能 |
|---|---|
| `blender.geometry_nodes.inspect` | 快照所有 Geometry Nodes 修改器 |
| `blender.geometry_nodes.validate` | 诊断 GN：Group Input/Output 存在性、几何输出连线 |
| `blender.geometry_nodes.ensure_basic_group` | 脚手架：Group Input → Group Output 最小 GN 修改器 |
| `blender.geometry_nodes.add_node` | 在几何节点组中添加节点 |
| `blender.geometry_nodes.connect_nodes` | 连接两个几何节点插口 |
| `blender.geometry_nodes.set_node_input` | 设置几何节点输入的默认值 |

#### Mesh 健康检查（v1.2.1 新增）
| Skill | 功能 |
|---|---|
| `blender.mesh.health_check` | 对选中/活动/全部对象运行网格诊断：非流形边、零面积面、孤立顶点、N-gon、未应用缩放 |

#### 文件生命周期（v1.2.1 新增）
| Skill | 功能 |
|---|---|
| `blender.file.save` | 保存 / 另存为 / 增量保存（`_001.blend` → `_002.blend`） |

#### 编辑操作（v1.2.1 新增）
| Skill | 功能 |
|---|---|
| `blender.edit.undo` | 撤销（支持 agent timer 上下文） |
| `blender.edit.redo` | 重做 |

#### Transform 变换（v1.2.1 新增）
| Skill | 功能 |
|---|---|
| `blender.transform.set` | 直接设置位置/旋转/缩放（无需 viewport 上下文） |
| `blender.transform.apply` | 应用位置/旋转/缩放 |
| `blender.transform.set_origin` | 设置原点（几何中心/游标/世界原点） |

#### 对象管理（v1.2.1 新增）
| Skill | 功能 |
|---|---|
| `blender.object.delete` | 删除对象 |
| `blender.object.duplicate` | 复制对象 |
| `blender.object.parent` | 设置父子关系 |
| `blender.object.organize_collection` | 将对象移入/移出集合 |

#### Agent 自省 & 开发者
| Skill | 功能 | 安全级别 |
|---|---|---|
| `blender.agent.list_skills` | 列出所有已注册 Skill 及描述 | 只读，自动 |
| `dev.run_python` | 执行任意 Python 代码（开发者模式） | ⚠️ 高危险，需确认 |

> 第三方插件可通过 `agent_skills.register()` 注册自己的 Skill 到 POPAgent（见下方「扩展集成」）。

### 🔌 多 LLM 提供商
| Provider | Streaming | Function Calling | 多模态图片 | 需 API Key |
|---|---|---|---|---|
| **OpenAI** (GPT-4o, GPT-4o-mini) | ✅ | ✅ | ✅ | ✅ |
| **DeepSeek** | ✅ (含思维链) | ✅ | — | ✅ |
| **Mimo** | ✅ | ✅ | — | ✅ |
| **minimax** (M3 / M2.7) | ✅ | ✅ | ✅ (minimax- 前缀模型) | ✅ |

> 视觉阅读当前视图需要先在 N 面板开启 Multimodal Images。开启后会显示图片输入区，支持 Ctrl+V 粘贴剪贴板图片/图片文件、选择当前 Blender 文件中的 Image datablock，或点击 + 从文件管理器选择图片。DeepSeek 和 Mimo 当前暂不支持多模态图片输入。

可在 Preferences 中即时切换，支持自定义 base URL（兼容私有部署）。

### 📝 对话管理
- 流式渲染（逐词显示回答）
- 自动保存对话历史（可收藏/删除/清空）
- 文本附件（支持从 Blender Text Editor 附加代码上下文）
- 图片附件（v1.2 新增：剪贴板 / 文件 / Blender Image datablock）
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
| **权限覆盖** | Preferences JSON 可针对单个 Skill 覆盖 `requires_confirmation` 级别 |
| **场景修改告知** | Skill 元数据标明 `modifies_scene` / `writes_files` / `launches_external_process` |
| **会话信任** | 首次确认后可在当前会话内标记为「信任」，不再弹窗 |
| **死循环检测** | 归一化工具签名，同一工具+参数连续调用 ≥3 次自动中止 |
| **模型超时保护** | 结构化 httpx.Timeout + asyncio.wait_for 双层保护 |
| **开发者模式** | `dev.run_python` 仅在 Preferences 开启「开发者模式」后可用，且每次执行都需确认 |
| **撤销支持** | 修改场景的 Skill 执行后自动推送 Ctrl+Z 撤销步骤 |

---

## 快速开始

### 1. 安装
将 `POPAgent` 目录放置到 Blender 的 addons 目录：

```
Windows: %APPDATA%\Blender Foundation\Blender\5.1\scripts\addons\
macOS:   ~/Library/Application Support/Blender/5.1/scripts/addons/
Linux:   ~/.config/blender/5.1/scripts/addons/
```

在 Blender 偏好设置 → Add-ons → 搜索 "POPAgent" → 勾选启用。

### 2. 配置 API Key
启用后，在 **3D View 侧栏 → POPAgent → Preferences（齿轮图标）** 中配置：

1. 选择 LLM 提供商（OpenAI / DeepSeek / Mimo / minimax）
2. 填入对应的 API Key 和 Base URL（如有需要）
3. 点击 **Check Dependencies** 安装 `httpx` 依赖
4. 点击 **Test Connection** 验证 API 连通性
5. （可选）在 System 中开启 **Stream** 以获得流式输出体验

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

你:   检查一下选中的 mesh 有没有问题

Agent: 🔍 对 3 个对象运行了健康检查：
       LOD_0 — ⚠️ 12 个 N-gon，1 条非流形边
       LOD_1 — ✅ 无问题
       LOD_2 — ⚠️ 未应用缩放
```

---

## 界面指南

### 面板结构（3D View → 侧栏 → POPAgent）

| 面板 | 说明 |
|---|---|
| **POPAgent** | 模型选择 + 输入框 + ▶ 发送 |
| **Answer** | 显示 AI 回答（文本/列表/代码）+ 执行追踪统计，流式更新 |
| **Attachments** | 管理文本/图片附件（粘贴、文件、Blender Image datablock） |
| **History** | 对话历史管理（收藏/删除/清空） |
| **Skills** | 查看/开关已注册的 Skill，管理会话信任，显示权限级别图标 |
| **Tokens** | Token 用量统计 + 人民币成本估算 |
| **Usage** | 场景用量记录 + CSV 导出 |
| **Links** | 相关链接 |

### Preferences（偏好设置）

| 区域 | 选项 |
|---|---|
| **API Keys** | OpenAI / DeepSeek / Mimo / minimax API Key 与 Base URL |
| **Read Aloud** | TTS 声线选择 |
| **Display** | 文字宽度微调 |
| **System** | 依赖管理、流式开关、模型超时、Agent 最大迭代次数、开发者模式、用量日志目录 |

---

## Agent 架构说明

```
用户输入
    │
    ▼
CHAT_COMPANION_OT_ask (AsyncModalOperatorMixin)
    │
    ├─ asyncio.gather()
    │   ├─ query_api()            ← LLM 调用 + Tool Call 循环
    │   ├─ print_answering_string()  ← UI 动画
    │   └─ print_waiting_string()    ← UI 动画
    │
query_api() → _agent_query()
    │
    ├─ 选择 Provider (OpenAI / DeepSeek / Mimo / minimax)
    ├─ skill_registry.all_skills() → provider.skills_to_tools()
    ├─ MessageBuilder 构造多轮消息（含图片附件）
    │
    └─ 工具调用循环（最多 15 轮，动态判定）
        ├─ agent_policy.choose_max_iters()      ← 动态轮数
        ├─ provider.build_request(messages, tools)
        ├─ run_with_model_timeout()             ← 超时保护
        ├─ LLM 返回 → provider.parse_response()
        ├─ 如果有 tool_calls:
        │   ├─ agent_policy.normalized_tool_signature()  ← 反死循环
        │   ├─ skill_registry.get_permission_level()     ← 权限门控
        │   ├─ executor.run(tc) → 主线程执行 skill handler
        │   ├─ execution_trace 记录耗时/成败
        │   └─ 结果追加到消息历史 → 继续循环
        └─ 如果没有 tool_calls:
            ├─ 最终文本回答 → 渲染到 UI
            ├─ execution_trace → Answer 面板统计
            ├─ usage_log 写入 JSONL
            └─ 保存到对话历史
```

### 项目模块

```
POPAgent/
├── __init__.py                  # 注册入口 (bl_info version 1.3.1)
├── agent_core/                 # Agent 核心
│   ├── skill_registry.py       # 全局 Skill 注册表 + 权限覆盖
│   ├── executor.py             # Skill 调度器（安全门控）
│   ├── confirm_dialog.py       # 用户确认弹窗 + 会话信任
│   ├── context_builder.py      # 场景上下文摘要生成
│   ├── message_builder.py      # 跨 Provider 消息构建（含图片）
│   ├── agent_policy.py         # 动态 max_iters / 归一化工具签名
│   ├── execution_trace.py      # 结构化执行追踪（v2 schema）
│   ├── usage_log.py            # JSONL 使用日志写入（v1.2.2）
│   ├── usage_mining.py         # 日志聚合/导出（v1.2.2）
│   ├── mesh_diagnostics.py     # 纯网格健康规则（v1.2.1）
│   ├── node_diagnostics.py     # 纯材质+GN诊断规则（v1.2.1）
│   ├── file_versioning.py      # 增量保存路径生成（v1.2.1）
│   ├── vision_inputs.py        # 图片附件收集（v1.2）
│   ├── retry.py                # 模型超时/重试策略
│   ├── main_thread.py          # 主线程任务队列 + bpy Timer
│   └── reverse_pull.py         # 延迟加载的第三方 Skill 补拉
├── builtin_skills/             # 内置 Skill 实现（32 个）
│   ├── blender_query.py        # 场景查询 / 截图 / API 搜索
│   ├── blender_select.py       # 对象选择 / 设活动
│   ├── blender_nodes.py        # 材质 + 几何节点编辑（v1.2.1）
│   ├── blender_mesh.py         # 网格健康检查（v1.2.1）
│   ├── blender_file.py         # 保存 / 增量保存（v1.2.1）
│   ├── blender_edit.py         # 撤销 / 重做（v1.2.1）
│   ├── blender_transform.py    # 变换 / 应用 / 原点（v1.2.1）
│   ├── blender_object.py       # 删除 / 复制 / 父级 / 集合（v1.2.1）
│   ├── agent_meta.py           # Agent 自省 Skill（v1.2.1）
│   └── dev_skills.py           # 开发者模式 (run_python)
├── providers/                  # LLM Provider 抽象层
│   ├── base.py                 # BaseProvider / StreamParser
│   ├── openai_compat.py        # OpenAI / DeepSeek / Mimo
│   └── anthropic.py            # Anthropic Messages API (drives minimax via the same protocol)
├── panels/                     # UI 面板
│   ├── panel_prompt.py         # 输入区
│   ├── panel_output.py         # 回答区（含执行追踪）
│   ├── panel_attachments.py    # 图片/文本附件管理
│   ├── panel_skills.py         # Skill 管理面板（权限图标）
│   ├── panel_tokens.py         # Token 用量 + 成本
│   └── ...
├── operators/                  # Blender Operators
│   ├── operator_ask.py         # 核心提问 + Agent 循环 + 追踪
│   ├── operator_skills.py      # Skill 开关 / 信任管理
│   ├── operator_usage.py       # 用量导出 / 日志挖掘
│   ├── operator_test_connection.py  # Provider 连通性测试
│   ├── operator_change_llm.py  # LLM 切换（含 Mimo）
│   ├── operator_image_attachments.py  # 图片附件管理
│   └── ...
├── properties/                 # PropertyGroups + Preferences
├── utils/                      # 异步循环 / 依赖管理 / 用量统计
├── usage_logs/                 # JSONL 使用日志（自动生成）
├── full/                       # Full 版功能（代码执行 / TTS / 界面帮助）
└── tests/                      # 单元测试
```

---

## 扩展集成

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

**如果想覆盖某个 Skill 的安全级别**，可以在 Preferences → System → Skill Permission Overrides 中写入 JSON：

```json
{"my_addon.do_something": "always"}
```

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
- 用量日志（`usage_logs/`）会在本地记录每次对话的 prompt 摘要和 token 消耗，导出 zip 时请确认不包含敏感内容

---

## FAQ

**Q: Agent 一直调用同一个工具怎么办？**
A: v1.2 内置了归一化死循环检测：相同工具+参数连续调用 ≥3 次会自动中止并返回提示。如果遇到误判，可以在对话中要求 agent「直接告诉我答案，不要调用工具」。

**Q: 为什么 Agent 没有调用任何工具？**
A: 检查 Skills 面板确认工具是否已启用（没有隐藏），以及 `agent_mode_enabled` 偏好是否开启（默认开启）。另外，部分简单问答（如"你好"）不需要工具。

**Q: 支持本地模型吗？**
A: 如果本地模型（如 Ollama / vLLM）提供 OpenAI 兼容的 `/v1/chat/completions` 接口并支持 Function Calling，可以在 Preferences 中设置自定义 Base URL 来使用。

**Q: 如何导出用量数据？**
A: 两种方式：(1) 在 Usage 面板点击 **Export CSV** 导出当前场景用量；(2) 在 Preferences 中点击 **Export Usage Logs** 一键打包所有 JSONL 日志为 zip，导出后自动归档清空。

**Q: 点击 "Check Dependencies" 失败？**
A: 按终端提示手动安装：
```
<Blender Python> -m pip install httpx --user
```
Blender Python 路径可在 Preferences → System 中找到。

**Q: Mimo 是什么？**
A: Mimo 是一个 OpenAI 兼容的模型提供商，支持 Function Calling 但不支持多模态图片输入。在 Preferences 中配置 Mimo API Key 和 Base URL 即可使用。

---

## License

GNU General Public License v2.0 or later — see [LICENSE.txt](LICENSE.txt).

POPAgent enables the use of LLMs from various providers. You must obtain your own API keys from them and therefore comply with their terms and privacy policies. The developer of this addon assumes no responsibility or liability for any misuse or damages resulting from its use.
