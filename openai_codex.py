"""
OpenAI Codex OAuth Wrapper

从 ~/.pi/agent/auth.json 读取 OAuth 凭证，调用 ChatGPT Codex API
Codex 使用的是 https://chatgpt.com/backend-api/codex/responses 端点
"""

import json
import time
import platform
import base64
import httpx
from pathlib import Path
from dataclasses import dataclass
from typing import Any, Generator


AUTH_FILE = Path.home() / ".pi" / "agent" / "auth.json"
OPENAI_TOKEN_URL = "https://auth.openai.com/oauth/token"
CODEX_API_URL = "https://chatgpt.com/backend-api/codex/responses"
CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"  # pi-ai 使用的 client id
JWT_CLAIM_PATH = "https://api.openai.com/auth"


@dataclass
class OAuthCredentials:
    access: str
    refresh: str
    expires: int
    account_id: str

    def is_expired(self) -> bool:
        # 提前 5 分钟认为过期
        return time.time() * 1000 > self.expires - 5 * 60 * 1000


def extract_account_id(token: str) -> str:
    """从 JWT token 中提取 account ID"""
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Invalid JWT token")

    # 解码 payload（需要 padding）
    payload_b64 = parts[1]
    padding = 4 - len(payload_b64) % 4
    if padding != 4:
        payload_b64 += "=" * padding

    payload = json.loads(base64.b64decode(payload_b64))
    account_id = payload.get(JWT_CLAIM_PATH, {}).get("chatgpt_account_id")
    if not account_id:
        raise ValueError("No account ID in token")
    return account_id


def load_credentials() -> OAuthCredentials | None:
    """从 auth.json 加载凭证"""
    if not AUTH_FILE.exists():
        print(f"Auth file not found: {AUTH_FILE}")
        print("Please run: npx @mariozechner/pi-ai login openai-codex")
        return None

    data = json.loads(AUTH_FILE.read_text())
    codex = data.get("openai-codex")
    if not codex:
        print("No openai-codex credentials found in auth.json")
        return None

    # 从 token 中提取 account_id（如果没有存储的话）
    account_id = codex.get("accountId", "")
    if not account_id:
        account_id = extract_account_id(codex["access"])

    return OAuthCredentials(
        access=codex["access"],
        refresh=codex["refresh"],
        expires=codex["expires"],
        account_id=account_id,
    )


def refresh_token(creds: OAuthCredentials) -> OAuthCredentials:
    """刷新 access token"""
    print("Refreshing access token...")

    resp = httpx.post(
        OPENAI_TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "refresh_token": creds.refresh,
            "client_id": CLIENT_ID,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    resp.raise_for_status()
    data = resp.json()

    new_access = data["access_token"]
    new_creds = OAuthCredentials(
        access=new_access,
        refresh=data.get("refresh_token", creds.refresh),
        expires=int(time.time() * 1000) + data["expires_in"] * 1000,
        account_id=extract_account_id(new_access),
    )

    # 保存新凭证
    save_credentials(new_creds)
    print("Token refreshed successfully")

    return new_creds


def save_credentials(creds: OAuthCredentials) -> None:
    """保存凭证到 auth.json"""
    data = json.loads(AUTH_FILE.read_text()) if AUTH_FILE.exists() else {}
    data["openai-codex"] = {
        "type": "oauth",
        "access": creds.access,
        "refresh": creds.refresh,
        "expires": creds.expires,
        "accountId": creds.account_id,
    }
    AUTH_FILE.parent.mkdir(parents=True, exist_ok=True)
    AUTH_FILE.write_text(json.dumps(data, indent=2))


def get_credentials() -> OAuthCredentials:
    """获取有效的凭证，自动处理 token 刷新"""
    creds = load_credentials()
    if not creds:
        raise RuntimeError("No credentials found")

    if creds.is_expired():
        creds = refresh_token(creds)

    return creds


def chat_completion(
    messages: list[dict[str, str]],
    model: str = "gpt-4o",
    system_prompt: str | None = None,
    stream: bool = False,
) -> dict[str, Any] | Generator[dict[str, Any], None, None]:
    """
    调用 ChatGPT Codex API

    Args:
        messages: 消息列表，格式 [{"role": "user", "content": "..."}]
        model: 模型名称，如 gpt-4o, gpt-4o-mini
        system_prompt: 系统提示词
        stream: 是否流式返回

    Returns:
        API 响应
    """
    creds = get_credentials()

    # 构建请求体 - 参考 pi-ai 的 buildRequestBody
    body = {
        "model": model,
        "stream": stream,
        "input": messages,
        "store": False,
        "instructions": system_prompt or "You are a helpful assistant.",
        "text": {"verbosity": "medium"},
        "include": ["reasoning.encrypted_content"],
        "tool_choice": "auto",
        "parallel_tool_calls": True,
    }

    # 构建 headers
    user_agent = f"pi ({platform.system()} {platform.release()}; {platform.machine()})"
    headers = {
        "Authorization": f"Bearer {creds.access}",
        "chatgpt-account-id": creds.account_id,
        "OpenAI-Beta": "responses=experimental",
        "originator": "pi",
        "User-Agent": user_agent,
        "Content-Type": "application/json",
        "Accept": "text/event-stream" if stream else "application/json",
    }

    if stream:
        return _stream_response(headers, body)
    else:
        return _sync_response(headers, body)


def _sync_response(headers: dict, body: dict) -> dict[str, Any]:
    """同步请求"""
    # 即使非流式，Codex API 也返回 SSE
    body["stream"] = True
    resp = httpx.post(CODEX_API_URL, headers=headers, json=body, timeout=60.0)
    resp.raise_for_status()

    # 解析 SSE 响应
    result = {"text": "", "model": body["model"], "usage": {}}
    for line in resp.text.split("\n"):
        if line.startswith("data:"):
            data = line[5:].strip()
            if data and data != "[DONE]":
                try:
                    event = json.loads(data)
                    _process_event(event, result)
                except json.JSONDecodeError:
                    pass

    return result


def _stream_response(
    headers: dict, body: dict
) -> Generator[dict[str, Any], None, None]:
    """流式请求"""
    with httpx.stream(
        "POST", CODEX_API_URL, headers=headers, json=body, timeout=60.0
    ) as resp:
        resp.raise_for_status()
        for line in resp.iter_lines():
            if line.startswith("data:"):
                data = line[5:].strip()
                if data and data != "[DONE]":
                    try:
                        event = json.loads(data)
                        yield event
                    except json.JSONDecodeError:
                        pass


def _process_event(event: dict, result: dict) -> None:
    """处理 SSE 事件"""
    event_type = event.get("type", "")

    if event_type == "response.output_text.delta":
        result["text"] += event.get("delta", "")

    elif event_type in ("response.done", "response.completed"):
        response = event.get("response", {})
        if "output" in response:
            for item in response["output"]:
                if item.get("type") == "message":
                    for content in item.get("content", []):
                        if content.get("type") == "output_text":
                            result["text"] = content.get("text", result["text"])
        if "usage" in response:
            result["usage"] = response["usage"]


def get_usage() -> dict[str, Any]:
    """获取 Codex 使用情况和额度信息"""
    creds = get_credentials()

    user_agent = f"pi ({platform.system()} {platform.release()}; {platform.machine()})"
    headers = {
        "Authorization": f"Bearer {creds.access}",
        "chatgpt-account-id": creds.account_id,
        "OpenAI-Beta": "responses=experimental",
        "originator": "pi",
        "User-Agent": user_agent,
    }

    resp = httpx.get(
        "https://chatgpt.com/backend-api/codex/usage", headers=headers, timeout=30.0
    )
    resp.raise_for_status()
    return resp.json()


def print_usage() -> None:
    """打印 Codex 使用情况"""
    usage = get_usage()

    print(f"Plan: {usage.get('plan_type', 'unknown')}")
    print(f"Email: {usage.get('email', 'unknown')}")

    # Credits
    credits = usage.get("credits", {})
    print(f"\nCredits:")
    print(f"  Balance: {credits.get('balance', '?')}")
    print(f"  Unlimited: {credits.get('unlimited', False)}")
    if credits.get("approx_local_messages"):
        print(f"  Approx local messages: {credits['approx_local_messages']}")
    if credits.get("approx_cloud_messages"):
        print(f"  Approx cloud messages: {credits['approx_cloud_messages']}")

    # Rate limits
    rate_limit = usage.get("rate_limit", {})
    print(f"\nRate Limit:")
    print(f"  Allowed: {rate_limit.get('allowed', '?')}")

    primary = rate_limit.get("primary_window", {})
    if primary:
        reset_mins = primary.get("reset_after_seconds", 0) // 60
        print(
            f"  Primary: {primary.get('used_percent', '?')}% used, resets in {reset_mins} min"
        )

    secondary = rate_limit.get("secondary_window", {})
    if secondary:
        reset_days = secondary.get("reset_after_seconds", 0) / 86400
        print(
            f"  Secondary: {secondary.get('used_percent', '?')}% used, resets in {reset_days:.1f} days"
        )


if __name__ == "__main__":
    print("\nTesting ChatGPT Codex API...")
    print(
        "Supported models: gpt-5.1, gpt-5.1-codex-mini, gpt-5.1-codex-max, gpt-5.2, gpt-5.2-codex"
    )
    print("-" * 40)

    # Codex API 只支持 GPT-5 系列模型
    result = chat_completion(
        messages=[{"role": "user", "content": "Say hello in 3 languages, be brief"}],
        model="gpt-5.1-codex-mini",  # 最便宜的 Codex 模型
    )

    print(result["text"])
    print("-" * 40)
    print(f"Model: {result['model']}")
    if result.get("usage"):
        print(f"Usage: {result['usage']}")

    print("\n" + "=" * 40)
    print("Checking Codex quota...")
    print("=" * 40)
    print_usage()
