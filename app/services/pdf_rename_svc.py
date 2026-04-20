"""PDF リネームサービス（1ファイル単位）"""

import json
import re
import shutil
from collections import Counter
from pathlib import Path
from typing import Callable, TypedDict

import anthropic

from .claude import call_claude, extract_text, pdf_to_images_b64, FatalApiError

PROMPT = """
以下のPDF書類から、次の4項目を抽出してください。

- doc_type: 書類の種類（請求書・注文書・見積書・納品書・領収書・その他 のいずれか）
- supplier_name: 発行元（仕入先・請求元・注文先）の会社名（例: 株式会社ABC）
- billing_month: 書類に記載されている年月（YYYYMM形式。例: 202604）
- total_with_tax: 税込合計金額（数値のみ、カンマなし。例: 550000。金額が不明または存在しない場合は空文字）

JSONオブジェクトのみ出力してください。説明文は不要です。
例: {"doc_type": "請求書", "supplier_name": "株式会社ABC", "billing_month": "202604", "total_with_tax": "550000"}
"""


class RenameResult(TypedDict):
    source: str
    status: str        # "ok" | "failed"
    dest_path: str     # 相対パス（PDF_RENAMED/ 以下）
    doc_type: str
    supplier: str
    month: str
    total: str
    reason: str


def _parse(raw: str) -> dict | None:
    m = re.search(r"\{.*?\}", raw, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group())
    except json.JSONDecodeError:
        return None


def _sanitize(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', "_", name).strip()


def rename_one(
    pdf_path: Path,
    client: anthropic.Anthropic,
    out_dir: Path,
    log_cb: Callable[[str, str], None],
) -> RenameResult:
    text = extract_text(pdf_path)
    images = [] if text.strip() else pdf_to_images_b64(pdf_path)

    attempts = call_claude(client, text.strip(), images, PROMPT, _parse, tries=3, log_cb=log_cb)

    if not attempts:
        log_cb("error", f"{pdf_path.name}: データ取得失敗")
        return RenameResult(source=pdf_path.name, status="failed", dest_path="",
                            doc_type="", supplier="", month="", total="",
                            reason="Claude からデータを取得できませんでした")

    def majority(field: str) -> str:
        vals = [r.get(field, "") for r in attempts if r.get(field, "")]
        return Counter(vals).most_common(1)[0][0] if vals else ""

    doc_type = _sanitize(majority("doc_type") or "不明")
    supplier = _sanitize(majority("supplier_name") or "不明")
    month    = majority("billing_month")
    total    = majority("total_with_tax")

    if not re.match(r"^\d{6}$", month):
        log_cb("warn", f"{pdf_path.name}: 年月の形式が不正 '{month}' → 失敗フォルダへ")
        fail_dir = out_dir / (month if re.match(r"^\d{6}$", month) else "不明")
        fail_dir.mkdir(parents=True, exist_ok=True)
        dest = fail_dir / f"失敗_{pdf_path.name}"
        if not dest.exists():
            shutil.copy2(pdf_path, dest)
        rel = str(dest.relative_to(out_dir))
        return RenameResult(source=pdf_path.name, status="failed", dest_path=rel,
                            doc_type=doc_type, supplier=supplier, month=month, total=total,
                            reason=f"年月の形式が不正: '{month}'")

    new_name = f"{doc_type}_{supplier}_{month}_{total}.pdf"
    dest_dir = out_dir / month
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / new_name

    if dest.exists():
        log_cb("info", f"{pdf_path.name}: スキップ（既存）→ {new_name}")
    else:
        shutil.copy2(pdf_path, dest)
        log_cb("success", f"{pdf_path.name} → {month}/{new_name}")

    return RenameResult(source=pdf_path.name, status="ok",
                        dest_path=str(dest.relative_to(out_dir)),
                        doc_type=doc_type, supplier=supplier, month=month, total=total,
                        reason="")
