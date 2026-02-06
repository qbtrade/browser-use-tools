"""
Browser-Use 兼容的 OpenAI Codex LLM

实现 browser-use 的 BaseChatModel Protocol
"""

import json
import platform
from typing import Any, TypeVar, overload

import httpx
from pydantic import BaseModel

from browser_use.llm.messages import BaseMessage
from browser_use.llm.views import ChatInvokeCompletion, ChatInvokeUsage
from browser_use.llm.schema import SchemaOptimizer

from openai_codex import get_credentials, CODEX_API_URL, OAuthCredentials

T = TypeVar("T", bound=BaseModel)


class ChatCodex:
    """Browser-Use 兼容的 ChatGPT Codex LLM"""

    def __init__(
        self,
        model: str = "gpt-5.1-codex-mini",
        timeout: float = 120.0,
    ):
        self.model = model
        self.timeout = timeout
        self._credentials: OAuthCredentials | None = None

    @property
    def provider(self) -> str:
        return "openai-codex"

    @property
    def name(self) -> str:
        return f"ChatCodex ({self.model})"

    @property
    def model_name(self) -> str:
        return self.model

    def _get_credentials(self) -> OAuthCredentials:
        if self._credentials is None:
            self._credentials = get_credentials()
        return self._credentials

    def _build_headers(self, creds: OAuthCredentials) -> dict[str, str]:
        user_agent = f"browser-use-codex ({platform.system()} {platform.release()})"
        return {
            "Authorization": f"Bearer {creds.access}",
            "chatgpt-account-id": creds.account_id,
            "OpenAI-Beta": "responses=experimental",
            "originator": "pi",
            "User-Agent": user_agent,
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }

    def _convert_messages(self, messages: list[BaseMessage]) -> tuple[str, list[dict]]:
        """将 browser-use messages 转换为 Codex API 格式"""
        system_prompt = "You are a helpful assistant."
        input_messages = []

        for msg in messages:
            # 处理 LangChain 消息对象和 dict
            if isinstance(msg, dict):
                role = msg.get("role", "user")
                content = msg.get("content", "")
            else:
                # LangChain 消息对象
                role = getattr(msg, "type", "user")
                if role == "human":
                    role = "user"
                elif role == "ai":
                    role = "assistant"
                content = getattr(msg, "content", "")

            if role == "system":
                system_prompt = content if isinstance(content, str) else str(content)
            else:
                # 处理多模态内容
                if isinstance(content, list):
                    # 提取文本内容
                    text_parts = []
                    for part in content:
                        if isinstance(part, dict):
                            # dict 格式
                            if part.get("type") == "text":
                                text_parts.append(part.get("text", ""))
                        elif isinstance(part, str):
                            text_parts.append(part)
                        elif hasattr(part, "type"):
                            # ContentPartTextParam / ContentPartImageParam 等类型对象
                            part_type = getattr(part, "type", None)
                            if part_type == "text":
                                text_parts.append(getattr(part, "text", ""))
                            # 跳过 image 类型
                    content = "\n".join(text_parts)

                input_messages.append({"role": role, "content": content})

        return system_prompt, input_messages

    @overload
    async def ainvoke(
        self, messages: list[BaseMessage], output_format: None = None, **kwargs: Any
    ) -> ChatInvokeCompletion[str]: ...

    @overload
    async def ainvoke(
        self, messages: list[BaseMessage], output_format: type[T], **kwargs: Any
    ) -> ChatInvokeCompletion[T]: ...

    async def ainvoke(
        self,
        messages: list[BaseMessage],
        output_format: type[T] | None = None,
        **kwargs: Any,
    ) -> ChatInvokeCompletion[T] | ChatInvokeCompletion[str]:
        """
        调用 Codex API

        Args:
            messages: 消息列表
            output_format: 可选的 Pydantic 模型类，用于结构化输出

        Returns:
            ChatInvokeCompletion 包含响应和 usage 信息
        """
        creds = self._get_credentials()
        system_prompt, input_messages = self._convert_messages(messages)

        # 如果需要结构化输出，修改 system prompt
        if output_format is not None:
            schema = SchemaOptimizer.create_optimized_json_schema(output_format)
            schema_str = json.dumps(schema, indent=2)
            system_prompt = f"""{system_prompt}

IMPORTANT: You must respond with a valid JSON object that matches this schema:
{schema_str}

Only output the JSON object, no other text."""

        body = {
            "model": self.model,
            "stream": True,
            "input": input_messages,
            "store": False,
            "instructions": system_prompt,
            "text": {"verbosity": "medium"},
            "include": ["reasoning.encrypted_content"],
            "tool_choice": "auto",
            "parallel_tool_calls": True,
        }

        headers = self._build_headers(creds)

        # 使用 httpx 异步客户端
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(CODEX_API_URL, headers=headers, json=body)
            response.raise_for_status()

            # 解析 SSE 响应
            text = ""
            usage_data = {}

            for line in response.text.split("\n"):
                if line.startswith("data:"):
                    data = line[5:].strip()
                    if data and data != "[DONE]":
                        try:
                            event = json.loads(data)
                            event_type = event.get("type", "")

                            if event_type == "response.output_text.delta":
                                text += event.get("delta", "")

                            elif event_type in ("response.done", "response.completed"):
                                resp = event.get("response", {})
                                if "output" in resp:
                                    for item in resp["output"]:
                                        if item.get("type") == "message":
                                            for content in item.get("content", []):
                                                if content.get("type") == "output_text":
                                                    text = content.get("text", text)
                                if "usage" in resp:
                                    usage_data = resp["usage"]
                        except json.JSONDecodeError:
                            pass

            # 构建 usage
            usage = ChatInvokeUsage(
                prompt_tokens=usage_data.get("input_tokens", 0),
                prompt_cached_tokens=usage_data.get("input_tokens_details", {}).get(
                    "cached_tokens"
                ),
                prompt_cache_creation_tokens=None,
                prompt_image_tokens=None,
                completion_tokens=usage_data.get("output_tokens", 0),
                total_tokens=usage_data.get("total_tokens", 0),
            )

            # 如果需要结构化输出，解析 JSON
            if output_format is not None:
                # 尝试提取 JSON
                try:
                    # 尝试直接解析
                    parsed_data = json.loads(text)
                except json.JSONDecodeError:
                    # 尝试从 markdown 代码块中提取
                    import re

                    json_match = re.search(
                        r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL
                    )
                    if json_match:
                        parsed_data = json.loads(json_match.group(1))
                    else:
                        raise ValueError(
                            f"Failed to parse JSON from response: {text[:200]}..."
                        )

                parsed = output_format.model_validate(parsed_data)
                return ChatInvokeCompletion(
                    completion=parsed, usage=usage, stop_reason="end_turn"
                )
            else:
                return ChatInvokeCompletion(
                    completion=text, usage=usage, stop_reason="end_turn"
                )


if __name__ == "__main__":
    import asyncio
    from pydantic import BaseModel

    class TestOutput(BaseModel):
        greetings: list[str]
        languages: list[str]

    async def test():
        print("Testing Browser-Use Codex...")
        print("-" * 40)

        llm = ChatCodex(model="gpt-5.1-codex-mini")

        # 测试简单调用
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Say hello in 3 languages, be brief"},
        ]
        result = await llm.ainvoke(messages)
        print(f"Simple response: {result.completion}")
        print(f"Usage: {result.usage}")

        print("-" * 40)

        # 测试结构化输出
        messages = [
            {"role": "user", "content": "Say hello in 3 languages"},
        ]
        result = await llm.ainvoke(messages, output_format=TestOutput)
        print(f"Structured response: {result.completion}")
        print(f"Usage: {result.usage}")

    asyncio.run(test())
