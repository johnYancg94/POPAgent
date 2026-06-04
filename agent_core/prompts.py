# POPAgent/agent_core/prompts.py
"""系统 prompt 具名常量 + 组装纯函数。不 import bpy，可裸 Python 测。

规则文本是从 operator_ask.py 的字符串拼接搬来的，搬移时一字不改。"""
from __future__ import annotations

# BASE_PRINCIPLES 与 chat_setup.system_instructions 同源。这里写死一份只在
# prompts.py 无法 import chat_setup（裸测环境）时作 fallback；运行时由
# build_system_prompt 的 base 参数注入真值，避免两份漂移。
BASE_PRINCIPLES = "You are POPAgent, an AI agent embedded inside Blender."
