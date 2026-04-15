"""
PDF2CSV 処理スクリプト
使い方: python process.py [--pdf-dir PDF2CSV/PDF] [--csv-dir PDF2CSV/CSV]

PDFフォルダ内の<客先名>サブフォルダを走査し、
PDFをOCRしてCSVフォルダに出力する。
"""

import os
import sys
import csv
import json
import base64
import argparse
import re
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# .env ファイルから環境変数を読み込む（スクリプトと同じディレクトリ）
load_dotenv(Path(__file__).parent / ".env")

# Windows コンソールの文字化け対策
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import pdfplumber
import fitz  # PyMuPDF
import anthropic

# ============================================================
# 設定
# ============================================================
BASE_DIR = Path(__file__).parent
DEFAULT_PDF_DIR = BASE_DIR / "PDF"
DEFAULT_CSV_DIR = BASE_DIR / "CSV"

# 抽出したい列の標準セット（追加は自動で行われる）
STANDARD_COLUMNS = [
    "source_file",       # 元PDFファイル名
    "processed_date",    # 処理日
    "client_name",       # 客先名（フォルダ名）
    "billing_month",     # 請求月
    "recipient",         # 宛先名
    "item_no",           # 明細番号
    "item_description",  # 明細項目
    "quantity",          # 数量
    "unit",              # 単位
    "unit_price",        # 単価
    "amount",            # 金額
    "tax",               # 消費税
    "subtotal",          # 小計
    "total",             # 合計
    "remarks",           # 備考
]

TABLE_DEF_FILENAME = "table_definition.csv"


# ============================================================
# テーブル定義書の読み書き
# ============================================================

def load_table_definition(csv_client_dir: Path) -> list[str]:
    """テーブル定義書を読み込む。なければ標準列を返す。"""
    def_path = csv_client_dir / TABLE_DEF_FILENAME
    if not def_path.exists():
        return list(STANDARD_COLUMNS)
    with open(def_path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return [row["column_name"] for row in reader if row.get("column_name")]


def save_table_definition(csv_client_dir: Path, columns: list[str]) -> None:
    """テーブル定義書を保存する。"""
    csv_client_dir.mkdir(parents=True, exist_ok=True)
    def_path = csv_client_dir / TABLE_DEF_FILENAME
    with open(def_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["column_name", "description", "example"])
        writer.writeheader()
        descriptions = {
            "source_file":       "元PDFファイル名",
            "processed_date":    "処理日 (YYYY-MM-DD)",
            "client_name":       "客先名（フォルダ名）",
            "billing_month":     "請求月 (YYYY-MM)",
            "recipient":         "宛先名",
            "item_no":           "明細番号",
            "item_description":  "明細項目名",
            "quantity":          "数量",
            "unit":              "単位",
            "unit_price":        "単価",
            "amount":            "金額",
            "tax":               "消費税",
            "subtotal":          "小計",
            "total":             "合計",
            "remarks":           "備考",
        }
        for col in columns:
            writer.writerow({
                "column_name": col,
                "description": descriptions.get(col, ""),
                "example": "",
            })
    print(f"  [定義書] 保存: {def_path}")


def update_columns_if_needed(
    csv_client_dir: Path, existing_columns: list[str], new_columns: list[str]
) -> list[str]:
    """新しい列が増えた場合、定義書を更新して既存CSVにも列を追加する。"""
    added = [c for c in new_columns if c not in existing_columns]
    if not added:
        return existing_columns

    print(f"  [定義書] 新列を追加: {added}")
    updated = existing_columns + added
    save_table_definition(csv_client_dir, updated)

    # 既存CSVに空列を追加
    for csv_file in csv_client_dir.glob("*.csv"):
        if csv_file.name == TABLE_DEF_FILENAME:
            continue
        _add_columns_to_csv(csv_file, added)

    return updated


def _add_columns_to_csv(csv_path: Path, new_columns: list[str]) -> None:
    """既存CSVファイルに空列を追加する。"""
    rows = []
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        existing_fields = reader.fieldnames or []
        rows = list(reader)

    all_fields = existing_fields + [c for c in new_columns if c not in existing_fields]
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=all_fields)
        writer.writeheader()
        for row in rows:
            for col in new_columns:
                row.setdefault(col, "")
            writer.writerow(row)
    print(f"  [CSV更新] 列追加: {csv_path.name}")


# ============================================================
# PDF テキスト抽出
# ============================================================

def extract_text_with_pdfplumber(pdf_path: Path) -> str:
    """pdfplumber でテキスト抽出を試みる。"""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            texts = []
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    texts.append(t)
            return "\n".join(texts)
    except Exception as e:
        print(f"  [pdfplumber] 失敗: {e}")
        return ""


def pdf_to_base64_images(pdf_path: Path) -> list[str]:
    """PyMuPDF でPDFの各ページをPNG画像に変換してBase64リストを返す。"""
    doc = fitz.open(str(pdf_path))
    images = []
    for page in doc:
        mat = fitz.Matrix(2.0, 2.0)  # 2倍解像度
        pix = page.get_pixmap(matrix=mat)
        images.append(base64.standard_b64encode(pix.tobytes("png")).decode())
    doc.close()
    return images


# ============================================================
# Claude API によるデータ抽出
# ============================================================

EXTRACTION_PROMPT = """
以下の請求書PDFの内容から、明細行ごとにデータを抽出してください。

抽出するフィールド:
- billing_month: 請求月 (YYYY-MM形式。例: 2026-03)
- recipient: 宛先名
- item_no: 明細番号（通し番号、なければ1から順に振る）
- item_description: 明細項目名
- quantity: 数量（数値のみ）
- unit: 単位（個、式、時間など）
- unit_price: 単価（数値のみ、カンマなし）
- amount: 金額（数値のみ、カンマなし）
- tax: 消費税（数値のみ、カンマなし。明細行に記載がなければ空）
- subtotal: 小計（数値のみ、カンマなし。ページ/書類全体の小計）
- total: 合計（数値のみ、カンマなし。書類全体の合計）
- remarks: 備考

出力形式: JSON配列（明細行ごとに1オブジェクト）
billing_month, recipient, subtotal, total は全行に同じ値を入れてください。
明細がない場合でも1行は出力してください。

例:
[
  {
    "billing_month": "2026-03",
    "recipient": "株式会社〇〇",
    "item_no": "1",
    "item_description": "システム開発費",
    "quantity": "1",
    "unit": "式",
    "unit_price": "500000",
    "amount": "500000",
    "tax": "",
    "subtotal": "500000",
    "total": "550000",
    "remarks": ""
  }
]

JSONのみ出力し、説明文は不要です。
"""


def extract_data_with_claude(pdf_path: Path, client: anthropic.Anthropic) -> list[dict]:
    """Claude Vision API でPDFからデータを抽出する。"""

    # まずテキスト抽出を試みる
    text = extract_text_with_pdfplumber(pdf_path)

    if text.strip():
        print(f"  [Claude] テキストPDFとして処理")
        message = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=4096,
            messages=[
                {
                    "role": "user",
                    "content": f"{EXTRACTION_PROMPT}\n\n--- PDF テキスト ---\n{text}",
                }
            ],
        )
        raw = message.content[0].text
    else:
        print(f"  [Claude] 画像PDFとして処理（Vision）")
        images = pdf_to_base64_images(pdf_path)
        content = []
        for img_b64 in images:
            content.append({
                "type": "image",
                "source": {"type": "base64", "media_type": "image/png", "data": img_b64},
            })
        content.append({"type": "text", "text": EXTRACTION_PROMPT})

        message = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=4096,
            messages=[{"role": "user", "content": content}],
        )
        raw = message.content[0].text

    # JSON抽出
    json_match = re.search(r"\[.*\]", raw, re.DOTALL)
    if not json_match:
        print(f"  [Claude] JSON取得失敗。生出力:\n{raw[:500]}")
        return []

    try:
        return json.loads(json_match.group())
    except json.JSONDecodeError as e:
        print(f"  [Claude] JSONパース失敗: {e}")
        return []


# ============================================================
# CSV 書き出し
# ============================================================

def write_csv(
    csv_path: Path,
    rows: list[dict],
    columns: list[str],
    client_name: str,
    source_file: str,
) -> None:
    """指定列順でCSVに書き出す。"""
    today = datetime.today().strftime("%Y-%m-%d")
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            row["source_file"] = source_file
            row["processed_date"] = today
            row["client_name"] = client_name
            # 定義済み列にないキーは extrasaction="ignore" で無視
            writer.writerow({col: row.get(col, "") for col in columns})
    print(f"  [CSV] 出力: {csv_path}")


# ============================================================
# メイン処理
# ============================================================

def process_client_folder(
    client_folder: Path,
    csv_dir: Path,
    claude_client: anthropic.Anthropic,
    force: bool = False,
) -> None:
    """1つの客先フォルダを処理する。"""
    client_name = client_folder.name
    csv_client_dir = csv_dir / f"{client_name}CSV"
    csv_client_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n=== 客先: {client_name} ===")

    # テーブル定義書の読み込み（なければ初回作成）
    first_run = not (csv_client_dir / TABLE_DEF_FILENAME).exists()
    columns = load_table_definition(csv_client_dir)

    pdf_files = sorted(client_folder.glob("*.pdf")) + sorted(client_folder.glob("*.PDF"))
    if not pdf_files:
        print(f"  PDFファイルが見つかりません: {client_folder}")
        return

    for pdf_path in pdf_files:
        # 出力先CSVのパス
        date_str = datetime.today().strftime("%Y%m%d")
        stem = pdf_path.stem
        out_csv = csv_client_dir / f"{date_str}_{stem}.csv"

        if out_csv.exists() and not force:
            print(f"  スキップ（処理済み）: {pdf_path.name}")
            continue

        print(f"  処理中: {pdf_path.name}")

        # データ抽出
        rows = extract_data_with_claude(pdf_path, claude_client)
        if not rows:
            print(f"  データ取得失敗: {pdf_path.name}")
            continue

        # 新列の検出・定義書更新
        extracted_cols = list(rows[0].keys()) if rows else []
        # source_file, processed_date, client_name は自動付加なので除外して比較
        auto_cols = {"source_file", "processed_date", "client_name"}
        new_user_cols = [c for c in extracted_cols if c not in columns and c not in auto_cols]
        if new_user_cols:
            columns = update_columns_if_needed(csv_client_dir, columns, new_user_cols)

        # 初回: テーブル定義書を作成
        if first_run:
            save_table_definition(csv_client_dir, columns)
            first_run = False

        # CSV書き出し
        write_csv(out_csv, rows, columns, client_name, pdf_path.name)

    print(f"  完了: {client_name}")


def main():
    parser = argparse.ArgumentParser(description="PDF → CSV 変換ツール")
    parser.add_argument("--pdf-dir", default=str(DEFAULT_PDF_DIR), help="PDFフォルダのパス")
    parser.add_argument("--csv-dir", default=str(DEFAULT_CSV_DIR), help="CSVフォルダのパス")
    parser.add_argument("--client", default=None, help="特定の客先名のみ処理")
    parser.add_argument("--force", action="store_true", help="処理済みファイルも再処理")
    args = parser.parse_args()

    pdf_dir = Path(args.pdf_dir)
    csv_dir = Path(args.csv_dir)

    if not pdf_dir.exists():
        print(f"PDFフォルダが見つかりません: {pdf_dir}")
        sys.exit(1)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("環境変数 ANTHROPIC_API_KEY が設定されていません。")
        sys.exit(1)

    claude_client = anthropic.Anthropic(api_key=api_key)

    # 客先フォルダを列挙
    client_folders = [
        d for d in sorted(pdf_dir.iterdir())
        if d.is_dir() and not d.name.startswith(".")
    ]

    if args.client:
        client_folders = [d for d in client_folders if d.name == args.client]
        if not client_folders:
            print(f"客先フォルダが見つかりません: {args.client}")
            sys.exit(1)

    if not client_folders:
        print(f"PDFフォルダ内に客先フォルダが見つかりません: {pdf_dir}")
        print("PDF/<客先名>/ フォルダを作成してPDFを入れてください。")
        sys.exit(0)

    print(f"PDF フォルダ: {pdf_dir}")
    print(f"CSV フォルダ: {csv_dir}")
    print(f"処理対象: {[d.name for d in client_folders]}")

    for folder in client_folders:
        process_client_folder(folder, csv_dir, claude_client, force=args.force)

    print("\n全処理完了。")


if __name__ == "__main__":
    main()
