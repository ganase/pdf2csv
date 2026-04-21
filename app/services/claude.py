"""
LLM 呼び出し統一層
- Anthropic SDK (Rakuten AI Gateway / Anthropic直)
- OpenAI互換 SDK (OpenAI, Gemini, RakutenAI via Gateway)
"""

import base64
import logging
from pathlib import Path
from typing import Callable, Any

import pdfplumber
import fitz

logging.getLogger("pdfminer").setLevel(logging.ERROR)


# ── プロバイダー定義 ────────────────────────────────────────────
PROVIDERS = {
    "rakuten_anthropic": {
        "label": "Rakuten Gateway (Anthropic)",
        "sdk": "anthropic",
        "base_url": "https://api.ai.public.rakuten-it.com/anthropic/",
        "models": [
            "claude-sonnet-4-6",
            "claude-sonnet-4-5-20250929",
            "claude-haiku-4-5-20251001",
        ],
        "default_model": "claude-sonnet-4-6",
    },
    "rakuten_openai": {
        "label": "Rakuten Gateway (OpenAI)",
        "sdk": "openai",
        "base_url": "https://api.ai.public.rakuten-it.com/openai/v1/",
        "models": [
            "gpt-5.4", "gpt-5.2", "gpt-5.1", "gpt-5",
            "gpt-5-mini", "gpt-5-nano", "gpt-5-chat-latest",
        ],
        "default_model": "gpt-5.1",
    },
    "rakuten_gemini": {
        "label": "Rakuten Gateway (Gemini)",
        "sdk": "openai",
        "base_url": "https://api.ai.public.rakuten-it.com/google-vertexai-us/oai-spec/v1/",
        "models": [
            "google/gemini-3.1-pro-preview",
            "google/gemini-3-flash-preview",
            "google/gemini-3.1-flash-lite-preview",
        ],
        "default_model": "google/gemini-3-flash-preview",
    },
    "rakuten_llm": {
        "label": "Rakuten AI",
        "sdk": "openai",
        "base_url": "https://api.ai.public.rakuten-it.com/rakutenllms/v1/",
        "models": [
            "rakutenai-2.0-mini",
            "rakutenai-2.0",
            "rakutenai-3.0",
        ],
        "default_model": "rakutenai-2.0",
    },
}

DEFAULT_PROVIDER = "rakuten_anthropic"


class FatalApiError(Exception):
    """処理を即時中断すべきAPIエラー（認証失敗・残高不足など）"""


def make_client(api_key: str, provider: str = DEFAULT_PROVIDER):
    """プロバイダーに応じたクライアントを生成して返す"""
    cfg = PROVIDERS.get(provider, PROVIDERS[DEFAULT_PROVIDER])
    if cfg["sdk"] == "anthropic":
        from anthropic import Anthropic
        return Anthropic(base_url=cfg["base_url"], auth_token=api_key)
    else:
        from openai import OpenAI
        return OpenAI(base_url=cfg["base_url"], api_key=api_key)


def extract_text(pdf_path: Path) -> str:
    try:
        with pdfplumber.open(pdf_path) as pdf:
            return "\n".join(p.extract_text() or "" for p in pdf.pages)
    except Exception:
        return ""


def pdf_to_images_b64(pdf_path: Path) -> list[str]:
    doc = fitz.open(str(pdf_path))
    images = []
    for page in doc:
        pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0))
        images.append(base64.standard_b64encode(pix.tobytes("png")).decode())
    doc.close()
    return images


def call_claude(
    client,
    text: str,
    images: list[str],
    prompt: str,
    parse_fn: Callable[[str], Any | None],
    tries: int = 3,
    log_cb: Callable[[str, str], None] | None = None,
    provider: str = DEFAULT_PROVIDER,
    model: str | None = None,
) -> list[Any]:
    """
    LLM を tries 回呼び出し、parse_fn で成功したものをリストで返す。
    FatalApiError は呼び出し元に伝播させる。
    """
    cfg = PROVIDERS.get(provider, PROVIDERS[DEFAULT_PROVIDER])
    resolved_model = model or cfg["default_model"]
    results = []

    for i in range(tries):
        try:
            raw = _call_once(client, cfg["sdk"], resolved_model, text, images, prompt)
        except Exception as e:
            err = str(e).lower()
            if any(k in err for k in ("authentication", "401", "invalid api key", "unauthorized")):
                raise FatalApiError("APIキーが無効です。設定画面でキーを確認してください。")
            if any(k in err for k in ("credit", "billing", "balance", "quota", "429")):
                raise FatalApiError("APIのクレジット残高またはレート制限に達しました。")
            if log_cb:
                log_cb("warn", f"試行 {i+1}/{tries} APIエラー: {e}")
            continue

        parsed = parse_fn(raw)
        if parsed is not None:
            results.append(parsed)
            if log_cb:
                log_cb("info", f"試行 {i+1}/{tries} 取得成功")
        else:
            if log_cb:
                log_cb("warn", f"試行 {i+1}/{tries} パース失敗")

    return results


def _call_once(client, sdk: str, model: str, text: str, images: list[str], prompt: str) -> str:
    """1回のLLM呼び出しを行い、テキストを返す"""
    if sdk == "anthropic":
        return _call_anthropic(client, model, text, images, prompt)
    else:
        return _call_openai(client, model, text, images, prompt)


def _call_anthropic(client, model: str, text: str, images: list[str], prompt: str) -> str:
    if text:
        msg = client.messages.create(
            model=model,
            max_tokens=4096,
            messages=[{"role": "user", "content": f"{prompt}\n\n--- PDF テキスト ---\n{text}"}],
        )
    else:
        content = [
            {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": img}}
            for img in images
        ]
        content.append({"type": "text", "text": prompt})
        msg = client.messages.create(
            model=model,
            max_tokens=4096,
            messages=[{"role": "user", "content": content}],
        )
    return msg.content[0].text


def _call_openai(client, model: str, text: str, images: list[str], prompt: str) -> str:
    if text:
        messages = [{"role": "user", "content": f"{prompt}\n\n--- PDF テキスト ---\n{text}"}]
    else:
        content = [
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{img}"},
            }
            for img in images
        ]
        content.append({"type": "text", "text": prompt})
        messages = [{"role": "user", "content": content}]

    resp = client.chat.completions.create(
        model=model,
        max_tokens=4096,
        messages=messages,
    )
    return resp.choices[0].message.content
