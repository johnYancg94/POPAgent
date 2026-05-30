# POPAgent 中文翻译字典
# =======================
# 通过 bpy.app.translations API 注册，Blender 自动匹配英文原文并替换。
# 翻译范围：UI 面板静态文本 + 首选项设置页
# 未翻译：技能名称/描述、Operator 状态栏消息、AI 生成内容

# 具名翻译 context：用于把 POPAgent 自己的短词（History/Usage/Clear/Add/Success 等）
# 与 Blender 内置同名词条区分开，避免误翻或被内置翻译覆盖。
# panel/menu 的 bl_translation_context 以及 layout.label(text_ctxt=...) 都引用它。
POPAGENT_CTX = "POPAgent"

# 简体中文词条表。Blender 4.0+ 用脚本制 locale `zh_HANS`（旧版本是 `zh_CN`），
# 下方 translations_dict 把同一份表同时挂到两个 key，新旧版本都能匹配。
_zh = {
        # ============================================================
        # 具名 context (POPAGENT_CTX) 下的词条
        # 这些文本在 UI 里带 text_ctxt / bl_translation_context = POPAGENT_CTX，
        # 必须用同一 context 作 key，否则匹配不上、仍显示英文。
        # ============================================================
        (POPAGENT_CTX, "History"): "历史记录",
        (POPAGENT_CTX, "Usage"): "用量",
        (POPAGENT_CTX, "Success"): "成功率",
        (POPAGENT_CTX, "Clear"): "清除",
        (POPAGENT_CTX, "Add"): "添加",
        (POPAGENT_CTX, "Add an attachment"): "添加附件",

        # ============================================================
        # Panel 标签 (bl_label / bl_category)
        # ============================================================
        ("*", "       POPAgent"): "       POPAgent",
        ("*", "        Answer"): "        回答",
        ("*", "POPAgent"): "POPAgent",
        ("*", "Skills"): "技能",
        ("*", "Usage"): "用量",

        # ============================================================
        # 首选项设置页 — addon_preferences.py
        # ============================================================

        # --- 页头 ---
        ("*", "Blender 5.1 Agent"): "Blender 5.1 智能体",

        # --- API 密钥 ---
        ("*", "API keys"): "API 密钥",
        ("*", "OpenAI API key"): "OpenAI API 密钥",
        ("*", "Base URL"): "基础 URL",
        ("*", "Get key"): "获取密钥",
        ("*", "API Docs"): "API 文档",
        ("*", "MiMo API key"): "MiMo API 密钥",
        ("*", "Model"): "模型",
        ("*", "DeepSeek API key"): "DeepSeek API 密钥",
        ("*", "Anthropic (Claude) API key"): "Anthropic (Claude) API 密钥",

        # --- 显示 ---
        ("*", "Display"): "显示",
        ("*", "Adjust Text Width"): "调整文本宽度",
        ("*", "Answer"): "回答显示",
        ("*", "Code Preview"): "代码预览",

        # --- 智能体模式 ---
        ("*", "Agent Mode"): "智能体模式",
        ("*", "Enable Agent"): "启用智能体",
        ("*", "Max Iterations"): "最大迭代次数",
        ("*", "Max History Context"): "最大历史上下文",
        ("*", "Blender API Docs"): "Blender API 文档",
        ("*", "URL"): "URL",
        ("*", "Local"): "本地",
        ("*", "Prefer Local"): "优先使用本地",

        # --- 用量日志 ---
        ("*", "Usage Log"): "用量日志",
        ("*", "Log Agent Usage"): "记录智能体用量",
        ("*", "Log Folder"): "日志文件夹",
        ("*", "Log Full Request Text"): "记录完整请求文本",

        # --- 系统 ---
        ("*", "System"): "系统",
        ("*", "Developer Mode"): "开发者模式",
        ("*", "Check Dependencies"): "检查依赖",
        ("*", "Dependencies installed."): "依赖已安装。",
        ("*", "Reinstall Dependencies"): "重新安装依赖",
        ("*", "Python installer pip not installed."): "Python 安装器 pip 未安装。",
        ("*", "Python module httpx not installed."): "Python 模块 httpx 未安装。",
        ("*", "Streaming not available, using All at Once."): "流式传输不可用，使用一次性返回。",
        ("*", "Install Dependencies"): "安装依赖",
        ("*", "Or install it manually"): "或手动安装",
        ("*", "How to install pip"): "如何安装 pip",
        ("*", "How to install httpx"): "如何安装 httpx",
        ("*", "All At Once"): "一次性返回",
        ("*", "Stream"): "流式传输",
        ("*", "Request Timeout"): "请求超时",

        # --- 免责声明 ---
        ("*", "Disclaimer"): "免责声明",
        ("*", "POPAgent enables the use of LLMs from various providers."):
            "POPAgent 允许使用来自不同提供商的 LLM。",
        ("*", "You must obtain your own API keys from them and therefore comply"):
            "您必须自行获取各提供商的 API 密钥，",
        ("*", "with their terms and privacy policies. The developer of this addon"):
            "并遵守其服务条款和隐私政策。",
        ("*", "assumes no responsibility or liability for any misuse or damages"):
            "本插件开发者对任何误用或由此产生的损害",
        ("*", "resulting from its use."):
            "不承担任何责任。",

        # ============================================================
        # 主输入面板 — panel_prompt.py
        # ============================================================
        ("*", "Multimodal Images"): "启用图像功能",
        ("*", "Test Connection"): "网络延迟测试",
        ("*", "Testing..."): "测试中...",
        ("*", "Images"): "图像",
        ("*", "Current model has image input disabled"):
            "当前模型未启用图像输入",
        ("*", "Paste, choose, or add an image"):
            "粘贴、选择或添加图像",
        ("*", "Please enter your API key in the addon preferences"):
            "请在插件首选项中输入您的 API 密钥",

        # ============================================================
        # 回答面板 — panel_output.py
        # ============================================================
        ("*", "Open Full"): "打开完整回答",
        ("*", "Copy Answer"): "复制回答",
        ("*", "Error Message"): "错误信息",
        ("*", "More Information"): "更多信息",
        ("*", "Ask to Fix Error"): "请求修复错误",

        # ============================================================
        # 附件面板 — panel_attachments.py
        # ============================================================
        ("*", "Attachments"): "附件",
        ("*", "All"): "全部",

        # ============================================================
        # 历史面板 — panel_history.py
        # ============================================================
        ("*", "History"): "历史记录",
        ("*", "Max Context"): "最大上下文",

        # ============================================================
        # 用量面板 — panel_tokens.py
        # ============================================================
        ("*", "Export Usage Logs"): "导出日志",
        ("*", "Weekly: click, save the .zip, send it in."):
            "每周：点击导出，保存 .zip 并提交。",
        ("*", "No usage recorded for this scene yet."):
            "此场景暂无用量记录。",
        ("*", "Ask POPAgent and this panel will fill in."):
            "向 POPAgent 提问后，此面板将显示数据。",
        ("*", "Scene Usage"): "场景用量",
        ("*", "Total tokens"): "Token 总数",
        ("*", "RMB cost"): "费用（元）",
        ("*", "Requests"): "请求数",
        ("*", "Success"): "成功率",
        ("*", "Average latency:"): "平均延迟：",
        ("*", "Token Breakdown"): "Token 明细",
        ("*", "Input"): "输入",
        ("*", "Output"): "输出",
        ("*", "Cache creation"): "缓存创建",
        ("*", "Cache read"): "缓存读取",
        ("*", "Reasoning"): "推理",
        ("*", "Recent Requests"): "最近请求",
        ("*", "Export CSV"): "导出 CSV",
        ("*", "Clear"): "清除",

        # ============================================================
        # 菜单 — menu_add_attachment.py / context_autocomplete.py
        # ============================================================
        ("*", "Add"): "添加",
        ("*", "Add an attachment"): "添加附件",
        ("*", "Attach Internal Text"): "附加内部文本",
        ("*", "Attach File..."): "附加文件...",
        ("*", "Full version:"): "完整版功能：",
        ("*", "Turn Comments into Code"): "将注释转为代码",
}

translations_dict = {
    "zh_HANS": _zh,  # Blender 4.0+ 简体中文真实 locale
    "zh_CN": _zh,    # 兼容 3.x 及更早
}
