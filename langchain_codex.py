"""
LangChain 兼容的 OpenAI Codex LLM

可以用于 browser-use 等需要 LangChain LLM 的库
"""

import json
import platform
from typing import Any, Iterator, List, Optional

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
import httpx

from openai_codex import get_credentials, CODEX_API_URL, OAuthCredentials


class ChatCodex(BaseChatModel):
    """LangChain 兼容的 ChatGPT Codex LLM"""

    model: str = "gpt-5.1-codex-mini"
    """模型名称"""

    model_name: str = "gpt-5.1-codex-mini"
    """模型名称（兼容性）"""

    streaming: bool = False
    """是否流式输出"""

    provider: str = "openai-codex"
    """Provider 名称（browser-use 需要）"""

    _credentials: Optional[OAuthCredentials] = None

    # 允许动态添加属性（browser-use 需要）
    model_config = {"extra": "allow"}

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # 同步 model 和 model_name
        if "model" in kwargs:
            self.model_name = kwargs["model"]
        elif "model_name" in kwargs:
            self.model = kwargs["model_name"]

    @property
    def _llm_type(self) -> str:
        return "codex"

    @property
    def _identifying_params(self) -> dict[str, Any]:
        return {"model": self.model}

    def _get_credentials(self) -> OAuthCredentials:
        if self._credentials is None:
            self._credentials = get_credentials()
        return self._credentials

    def _build_headers(self, creds: OAuthCredentials) -> dict[str, str]:
        user_agent = f"langchain-codex ({platform.system()} {platform.release()})"
        return {
            "Authorization": f"Bearer {creds.access}",
            "chatgpt-account-id": creds.account_id,
            "OpenAI-Beta": "responses=experimental",
            "originator": "pi",
            "User-Agent": user_agent,
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }

    def _convert_messages(self, messages: List[BaseMessage]) -> tuple[str, list[dict]]:
        """将 LangChain messages 转换为 Codex API 格式"""
        system_prompt = "You are a helpful assistant."
        input_messages = []

        for msg in messages:
            if isinstance(msg, SystemMessage):
                system_prompt = msg.content
            elif isinstance(msg, HumanMessage):
                input_messages.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                input_messages.append({"role": "assistant", "content": msg.content})

        return system_prompt, input_messages

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """生成响应"""
        creds = self._get_credentials()
        system_prompt, input_messages = self._convert_messages(messages)

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
        resp = httpx.post(CODEX_API_URL, headers=headers, json=body, timeout=120.0)
        resp.raise_for_status()

        # 解析 SSE 响应
        text = ""
        usage = {}
        for line in resp.text.split("\n"):
            if line.startswith("data:"):
                data = line[5:].strip()
                if data and data != "[DONE]":
                    try:
                        event = json.loads(data)
                        event_type = event.get("type", "")
                        if event_type == "response.output_text.delta":
                            delta = event.get("delta", "")
                            text += delta
                            if run_manager:
                                run_manager.on_llm_new_token(delta)
                        elif event_type in ("response.done", "response.completed"):
                            response = event.get("response", {})
                            if "output" in response:
                                for item in response["output"]:
                                    if item.get("type") == "message":
                                        for content in item.get("content", []):
                                            if content.get("type") == "output_text":
                                                text = content.get("text", text)
                            if "usage" in response:
                                usage = response["usage"]
                    except json.JSONDecodeError:
                        pass

        message = AIMessage(content=text)
        generation = ChatGeneration(message=message)

        return ChatResult(
            generations=[generation],
            llm_output={"usage": usage, "model": self.model},
        )

    def _stream(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        """流式生成响应"""
        creds = self._get_credentials()
        system_prompt, input_messages = self._convert_messages(messages)

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

        with httpx.stream(
            "POST", CODEX_API_URL, headers=headers, json=body, timeout=120.0
        ) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if line.startswith("data:"):
                    data = line[5:].strip()
                    if data and data != "[DONE]":
                        try:
                            event = json.loads(data)
                            event_type = event.get("type", "")
                            if event_type == "response.output_text.delta":
                                delta = event.get("delta", "")
                                chunk = ChatGenerationChunk(
                                    message=AIMessage(content=delta)
                                )
                                if run_manager:
                                    run_manager.on_llm_new_token(delta)
                                yield chunk
                        except json.JSONDecodeError:
                            pass


if __name__ == "__main__":
    # 测试 LangChain Codex
    print("Testing LangChain Codex...")
    print("-" * 40)

    llm = ChatCodex(model="gpt-5.1-codex-mini")

    messages = [
        SystemMessage(content="You are a helpful assistant."),
        HumanMessage(content="Say hello in 3 languages, be brief"),
    ]

    result = llm.invoke(messages)
    print(result.content)
    print("-" * 40)
