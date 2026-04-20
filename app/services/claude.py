"""
共通 Claude API ユーティリティ
- テキスト/画像抽出
- 複数回呼び出し + パース（多数決は各サービス側で実施）
"""

import base64
import logging
from pathlib import Path
from typing import Callable, Any

import pdfplumber
import fitz
import anthropic
from anthropic import Anthropic

GATEWAY_BASE_URL = "https://api.ai.public.rakuten-it.com/anthropic/"
MODEL = "claude-sonnet-4-6"


def make_client(api_key: str) -> Anthropic:
    return Anthropic(
        base_url=GATEWAY_BASE_URL,
        auth_token=api_key,
    )

logging.getLogger("pdfminer").setLevel(logging.ERROR)


class FatalApiError(Exception):
    """処理を即時中断すべきAPIエラー（認証失敗・残高不足など）"""


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
    client: anthropic.Anthropic,
    text: str,
    images: list[str],
    prompt: str,
    parse_fn: Callable[[str], Any | None],
    tries: int = 3,
    log_cb: Callable[[str, str], None] | None = None,
) -> list[Any]:
    """
    Claude を tries 回呼び出し、parse_fn で成功したものをリストで返す。
    FatalApiError は呼び出し元に伝播させる。
    """
    results = []
    for i in range(tries):
        try:
            if text:
                msg = client.messages.create(
                    model=MODEL,
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
                    model=MODEL,
                    max_tokens=4096,
                    messages=[{"role": "user", "content": content}],
                )
        except anthropic.AuthenticationError:
            raise FatalApiError("APIキーが無効です。設定画面で ANTHROPIC_API_KEY を確認してください。")
        except anthropic.PermissionDeniedError as e:
            msg_str = str(e).lower()
            if any(k in msg_str for k in ("credit", "billing", "balance")):
                raise FatalApiError("Anthropic APIのクレジット残高が不足しています。")
            raise FatalApiError(f"APIアクセスが拒否されました: {e}")
        except anthropic.APIError as e:
            if log_cb:
                log_cb("warn", f"試行 {i+1}/{tries} APIエラー: {e}")
            continue

        parsed = parse_fn(msg.content[0].text)
        if parsed is not None:
            results.append(parsed)
            if log_cb:
                log_cb("info", f"試行 {i+1}/{tries} 取得成功")
        else:
            if log_cb:
                log_cb("warn", f"試行 {i+1}/{tries} パース失敗")

    return results
