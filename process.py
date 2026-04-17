"""
PDF2CSV 処理スクリプト
使い方: python process.py [--pdf-dir PDF/] [--csv-dir CSV/]

PDFフォルダ内の全PDFをClaudeで読み取り、
CSV/<YYYYMM>/請求書_YYYYMM.csv に月別で集約する。
"""

import os
import sys
import csv
import json
import base64
import argparse
import re
import logging
from collections import Counter
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

logging.getLogger("pdfminer").setLevel(logging.ERROR)

import pdfplumber
import fitz
import anthropic

BASE_DIR = Path(__file__).parent
DEFAULT_PDF_DIR = BASE_DIR / "PDF"
DEFAULT_CSV_DIR = BASE_DIR / "CSV"

SKIP_FOLDERS = {"samples"}

# 出力CSV の列定義（順序固定）
COLUMNS = [
    "処理日",       # 処理した日付
    "元ファイル名", # 元PDFのファイル名
    "仕入先名",     # 請求元会社名
    "請求年月",     # YYYY-MM
    "書類区分",     # 請求書・注文書・見積書など
    "明細番号",     # 行番号
    "品目・摘要",   # 明細の内容
    "数量",
    "単位",
    "単価",
    "金額",
    "消費税",
    "合計（税込）", # 書類全体の税込合計
    "備考",
]

TRIES = 3

EXTRACTION_PROMPT = """
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

例:
[
  {
    "doc_type": "請求書",
    "supplier_name": "株式会社ABC",
    "billing_month": "2026-04",
    "item_no": "1",
    "item_description": "システム開発費",
    "quantity": "1",
    "unit": "式",
    "unit_price": "500000",
    "amount": "500000",
    "tax": "",
    "total_with_tax": "550000",
    "remarks": ""
  }
]
"""


# ============================================================
# PDF テキスト / 画像抽出
# ============================================================

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


# ============================================================
# Claude API 呼び出し（多数決）
# ============================================================

def _call_claude(client: anthropic.Anthropic, text: str, images: list[str]) -> list[dict] | None:
    try:
        if text:
            msg = client.messages.create(
                model="claude-opus-4-6",
                max_tokens=4096,
                messages=[{"role": "user", "content": f"{EXTRACTION_PROMPT}\n\n--- PDF テキスト ---\n{text}"}],
            )
        else:
            content = [
                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": img}}
                for img in images
            ]
            content.append({"type": "text", "text": EXTRACTION_PROMPT})
            msg = client.messages.create(
                model="claude-opus-4-6",
                max_tokens=4096,
                messages=[{"role": "user", "content": content}],
            )
    except anthropic.AuthenticationError:
        print("\nエラー: APIキーが無効です。.env の ANTHROPIC_API_KEY を確認してください。")
        sys.exit(1)
    except anthropic.PermissionDeniedError:
        print("\nエラー: APIアクセスが拒否されました。クレジット残高を確認してください。")
        sys.exit(1)
    except anthropic.APIError as e:
        print(f"  [Claude] APIエラー: {e}")
        return None

    raw = msg.content[0].text
    m = re.search(r"\[.*\]", raw, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group())
    except json.JSONDecodeError:
        return None


def extract_rows(pdf_path: Path, client: anthropic.Anthropic) -> list[dict] | None:
    """TRIES回呼び出し、明細行を多数決で確定する。"""
    text = extract_text(pdf_path)
    images = [] if text.strip() else pdf_to_images_b64(pdf_path)

    attempts = []
    for i in range(TRIES):
        rows = _call_claude(client, text.strip(), images)
        if rows:
            attempts.append(rows)
            print(f"  [試行 {i+1}/{TRIES}] {len(rows)}行取得")
        else:
            print(f"  [試行 {i+1}/{TRIES}] 取得失敗")

    if not attempts:
        return None

    # 行数の多数決で代表セットを選ぶ
    row_counts = Counter(len(a) for a in attempts)
    best_count = row_counts.most_common(1)[0][0]
    candidates = [a for a in attempts if len(a) == best_count]

    # フィールドごとに多数決
    merged = []
    for row_idx in range(best_count):
        merged_row = {}
        for field in candidates[0][row_idx].keys():
            vals = [c[row_idx].get(field, "") for c in candidates if c[row_idx].get(field, "")]
            merged_row[field] = Counter(vals).most_common(1)[0][0] if vals else ""
        merged.append(merged_row)

    return merged


# ============================================================
# CSV 書き出し
# ============================================================

def append_to_monthly_csv(csv_path: Path, rows: list[dict], source_file: str) -> None:
    """月別CSVに明細行を追記する。ファイルがなければヘッダーも書く。"""
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
    print(f"  [CSV] 追記: {csv_path.name}  ({len(rows)}行)")


# ============================================================
# メイン処理
# ============================================================

class FatalApiError(Exception):
    pass


def process_pdf(pdf_path: Path, csv_dir: Path, client: anthropic.Anthropic, force: bool) -> bool:
    print(f"  処理中: {pdf_path.name}")
    rows = extract_rows(pdf_path, client)

    if not rows:
        print(f"  [失敗] データ取得できず: {pdf_path.name}")
        return False

    # 請求年月を確定（全行同じはずなので先頭行から取得）
    billing_month = rows[0].get("billing_month", "")
    m = re.match(r"^(\d{4})-(\d{2})$", billing_month)
    if not m:
        print(f"  [失敗] 請求年月の形式が不正: '{billing_month}'")
        return False

    month_folder = m.group(1) + m.group(2)  # YYYYMM
    csv_month_dir = csv_dir / month_folder
    csv_month_dir.mkdir(parents=True, exist_ok=True)
    csv_path = csv_month_dir / f"請求書_{month_folder}.csv"

    # force=False のとき、既にこのファイルが記録済みかチェック
    if not force and csv_path.exists():
        with open(csv_path, encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            if any(r.get("元ファイル名") == pdf_path.name for r in reader):
                print(f"  スキップ（処理済み）: {pdf_path.name}")
                return True

    append_to_monthly_csv(csv_path, rows, pdf_path.name)
    return True


def main():
    parser = argparse.ArgumentParser(description="PDF → CSV 変換ツール")
    parser.add_argument("--pdf-dir", default=str(DEFAULT_PDF_DIR))
    parser.add_argument("--csv-dir", default=str(DEFAULT_CSV_DIR))
    parser.add_argument("--force", action="store_true", help="処理済みファイルも再処理")
    args = parser.parse_args()

    pdf_dir = Path(args.pdf_dir)
    csv_dir = Path(args.csv_dir)

    if not pdf_dir.exists():
        print(f"PDFフォルダが見つかりません: {pdf_dir}")
        sys.exit(1)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("エラー: ANTHROPIC_API_KEY が設定されていません。.env ファイルを確認してください。")
        input("\nEnter キーで終了...")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    pdf_files = []
    for path in pdf_dir.rglob("*.pdf"):
        if not any(part in SKIP_FOLDERS for part in path.parts):
            pdf_files.append(path)
    for path in pdf_dir.rglob("*.PDF"):
        if not any(part in SKIP_FOLDERS for part in path.parts):
            pdf_files.append(path)

    if not pdf_files:
        print(f"PDFファイルが見つかりません: {pdf_dir}")
        input("\nEnter キーで終了...")
        sys.exit(0)

    print(f"PDF フォルダ: {pdf_dir}")
    print(f"CSV フォルダ: {csv_dir}")
    print(f"対象ファイル数: {len(pdf_files)}\n")

    ok = ng = 0
    for pdf in sorted(set(pdf_files)):
        if process_pdf(pdf, csv_dir, client, args.force):
            ok += 1
        else:
            ng += 1

    print(f"\n完了: 成功 {ok} 件 / 失敗 {ng} 件")
    print(f"出力フォルダ: {csv_dir}")
    input("\nEnter キーで終了...")


if __name__ == "__main__":
    main()
