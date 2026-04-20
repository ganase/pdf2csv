"""PDF → CSV 変換サービス（1ファイル単位）"""

import csv
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Callable, TypedDict

import anthropic

from .claude import call_claude, extract_text, pdf_to_images_b64, FatalApiError

COLUMNS = [
    "処理日", "元ファイル名", "仕入先名", "請求年月", "書類区分",
    "明細番号", "品目・摘要", "数量", "単位", "単価", "金額",
    "消費税", "合計（税込）", "備考",
]

PROMPT = """
以下のPDF書類から、明細行ごとにデータを抽出してください。

抽出するフィールド:
- doc_type: 書類区分（請求書・注文書・見積書・納品書・領収書・その他）
- supplier_name: 発行元（仕入先・請求元）の会社名
- billing_month: 請求年月（YYYY-MM形式。例: 2026-04）
- item_no: 明細番号（なければ1から順番）
- item_description: 品目・摘要
- quantity: 数量（数値のみ）
- unit: 単位（個・式・時間など）
- unit_price: 単価（数値のみ、カンマなし）
- amount: 金額（数値のみ、カンマなし）
- tax: 消費税（数値のみ、カンマなし。明細行になければ空）
- total_with_tax: 税込合計（数値のみ、カンマなし。書類全体の合計。全行同じ値）
- remarks: 備考

出力形式: JSONの配列（明細行ごとに1オブジェクト）
doc_type・supplier_name・billing_month・total_with_tax は全行に同じ値を入れてください。
明細がない場合でも1行は出力してください。
JSONのみ出力し、説明文は不要です。
"""


class ProcessResult(TypedDict):
    source: str
    status: str          # "ok" | "skipped" | "failed"
    csv_path: str        # 相対パス（CSV/ 以下）
    billing_month: str   # YYYY-MM
    rows_written: int
    reason: str


def _parse(raw: str) -> list[dict] | None:
    m = re.search(r"\[.*\]", raw, re.DOTALL)
    if not m:
        return None
    try:
        result = json.loads(m.group())
        return result if isinstance(result, list) and result else None
    except json.JSONDecodeError:
        return None


def _append_csv(csv_path: Path, rows: list[dict], source_file: str) -> int:
    today = datetime.today().strftime("%Y-%m-%d")
    exists = csv_path.exists()
    with open(csv_path, "a", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
        if not exists:
            writer.writeheader()
        for row in rows:
            writer.writerow({
                "処理日":       today,
                "元ファイル名": source_file,
                "仕入先名":     row.get("supplier_name", ""),
                "請求年月":     row.get("billing_month", ""),
                "書類区分":     row.get("doc_type", ""),
                "明細番号":     row.get("item_no", ""),
                "品目・摘要":   row.get("item_description", ""),
                "数量":         row.get("quantity", ""),
                "単位":         row.get("unit", ""),
                "単価":         row.get("unit_price", ""),
                "金額":         row.get("amount", ""),
                "消費税":       row.get("tax", ""),
                "合計（税込）": row.get("total_with_tax", ""),
                "備考":         row.get("remarks", ""),
            })
    return len(rows)


def process_one(
    pdf_path: Path,
    client: anthropic.Anthropic,
    csv_dir: Path,
    log_cb: Callable[[str, str], None],
    force: bool = False,
) -> ProcessResult:
    text = extract_text(pdf_path)
    images = [] if text.strip() else pdf_to_images_b64(pdf_path)

    attempts = call_claude(client, text.strip(), images, PROMPT, _parse, tries=3, log_cb=log_cb)

    if not attempts:
        log_cb("error", f"{pdf_path.name}: データ取得失敗")
        return ProcessResult(source=pdf_path.name, status="failed", csv_path="",
                             billing_month="", rows_written=0,
                             reason="Claude からデータを取得できませんでした")

    # 行数多数決で代表セットを選択
    row_counts = Counter(len(a) for a in attempts)
    best_n = row_counts.most_common(1)[0][0]
    candidates = [a for a in attempts if len(a) == best_n]

    merged = []
    for idx in range(best_n):
        merged_row = {}
        for field in candidates[0][idx].keys():
            vals = [c[idx].get(field, "") for c in candidates if c[idx].get(field, "")]
            merged_row[field] = Counter(vals).most_common(1)[0][0] if vals else ""
        merged.append(merged_row)

    billing_month = merged[0].get("billing_month", "")
    m = re.match(r"^(\d{4})-(\d{2})$", billing_month)
    if not m:
        log_cb("error", f"{pdf_path.name}: 請求年月の形式が不正 '{billing_month}'")
        return ProcessResult(source=pdf_path.name, status="failed", csv_path="",
                             billing_month=billing_month, rows_written=0,
                             reason=f"請求年月の形式が不正: '{billing_month}'")

    month_folder = m.group(1) + m.group(2)
    csv_month_dir = csv_dir / month_folder
    csv_month_dir.mkdir(parents=True, exist_ok=True)
    csv_path = csv_month_dir / f"請求書_{month_folder}.csv"
    rel_path = f"{month_folder}/請求書_{month_folder}.csv"

    if not force and csv_path.exists():
        with open(csv_path, encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            if any(r.get("元ファイル名") == pdf_path.name for r in reader):
                log_cb("info", f"{pdf_path.name}: スキップ（処理済み）")
                return ProcessResult(source=pdf_path.name, status="skipped",
                                     csv_path=rel_path, billing_month=billing_month,
                                     rows_written=0, reason="処理済み")

    n = _append_csv(csv_path, merged, pdf_path.name)
    log_cb("success", f"{pdf_path.name} → {rel_path} ({n}行)")
    return ProcessResult(source=pdf_path.name, status="ok", csv_path=rel_path,
                         billing_month=billing_month, rows_written=n, reason="")
