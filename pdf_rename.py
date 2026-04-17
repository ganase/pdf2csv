"""
PDF リネーム & 月別整理スクリプト
- PDF フォルダ内の全 PDF を対象に Claude で内容を読み取る
- 仕入先会社名_請求年月_税込金額.pdf にリネームしてコピー
- PDF_RENAMED/<YYYYMM>/ フォルダに整理（オリジナルはそのまま）
"""

import os
import sys
import json
import base64
import re
import shutil
import logging
from collections import Counter
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# pdfminer の FontBBox 警告を抑制
logging.getLogger("pdfminer").setLevel(logging.ERROR)

import pdfplumber
import fitz
import anthropic

BASE_DIR = Path(__file__).parent
PDF_DIR = BASE_DIR / "PDF"
OUT_DIR = BASE_DIR / "PDF_RENAMED"

SKIP_FOLDERS = {"samples"}

EXTRACTION_PROMPT = """
以下のPDF書類から、次の4項目を抽出してください。

- doc_type: 書類の種類（請求書・注文書・見積書・納品書・領収書・その他 のいずれか）
- supplier_name: 発行元（仕入先・請求元・注文先）の会社名（例: 株式会社ABC）
- billing_month: 書類に記載されている年月（YYYYMM形式。例: 202604）
- total_with_tax: 税込合計金額（数値のみ、カンマなし。例: 550000。金額が不明または存在しない場合は空文字）

JSONオブジェクトのみ出力してください。説明文は不要です。

例:
{"doc_type": "請求書", "supplier_name": "株式会社ABC", "billing_month": "202604", "total_with_tax": "550000"}
"""


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


TRIES = 3  # Claude に何回問い合わせて多数決を取るか


def _call_claude(client: anthropic.Anthropic, text: str, images: list[str]) -> dict | None:
    """Claude を1回呼び出してJSONを返す。パース失敗時は None。"""
    try:
        if text:
            msg = client.messages.create(
                model="claude-opus-4-6",
                max_tokens=512,
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
                max_tokens=512,
                messages=[{"role": "user", "content": content}],
            )
    except anthropic.AuthenticationError:
        print("\n[エラー] APIキーが無効です。.env の ANTHROPIC_API_KEY を確認してください。")
        sys.exit(1)
    except anthropic.PermissionDeniedError:
        print("\n[エラー] APIアクセスが拒否されました。クレジット残高を確認してください。")
        sys.exit(1)
    except anthropic.APIError as e:
        print(f"  [Claude] APIエラー: {e}")
        return None

    raw = msg.content[0].text
    m = re.search(r"\{.*?\}", raw, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group())
    except json.JSONDecodeError:
        return None


def extract_info(pdf_path: Path, client: anthropic.Anthropic) -> dict | None:
    """TRIES 回呼び出し、各フィールドを多数決で確定する。"""
    text = extract_text(pdf_path)
    images = [] if text.strip() else pdf_to_images_b64(pdf_path)

    results = []
    for i in range(TRIES):
        r = _call_claude(client, text.strip(), images)
        if r:
            results.append(r)
            print(f"  [試行 {i+1}/{TRIES}] {r}")
        else:
            print(f"  [試行 {i+1}/{TRIES}] 取得失敗")

    if not results:
        return None

    # フィールドごとに多数決
    def majority(field: str) -> str:
        vals = [r.get(field, "") for r in results if r.get(field, "")]
        if not vals:
            return ""
        return Counter(vals).most_common(1)[0][0]

    return {
        "doc_type":       majority("doc_type"),
        "supplier_name":  majority("supplier_name"),
        "billing_month":  majority("billing_month"),
        "total_with_tax": majority("total_with_tax"),
    }


def sanitize(name: str) -> str:
    """ファイル名に使えない文字を除去する。"""
    return re.sub(r'[\\/:*?"<>|]', "_", name).strip()


def copy_file(src: Path, dest: Path) -> None:
    if dest.exists():
        print(f"  スキップ（既存）: {dest.name}")
        return
    shutil.copy2(src, dest)
    print(f"  → {dest}")


def process(pdf_path: Path, client: anthropic.Anthropic) -> bool:
    print(f"  処理中: {pdf_path.name}")
    info = extract_info(pdf_path, client)

    # 抽出失敗 or 年月が不正 → 失敗フォルダへ
    month = (info or {}).get("billing_month", "")
    if not info or not re.match(r"^\d{6}$", month):
        reason = "抽出失敗" if not info else f"年月不正: '{month}'"
        print(f"  [失敗] {reason} → 失敗ファイルとして出力")
        fail_dir = OUT_DIR / (month if re.match(r"^\d{6}$", month) else "不明")
        fail_dir.mkdir(parents=True, exist_ok=True)
        copy_file(pdf_path, fail_dir / f"失敗_{pdf_path.name}")
        return False

    doc_type = sanitize(info.get("doc_type", "不明"))
    supplier = sanitize(info.get("supplier_name", "不明"))
    total = info.get("total_with_tax", "")

    new_name = f"{doc_type}_{supplier}_{month}_{total}.pdf"
    dest_dir = OUT_DIR / month
    dest_dir.mkdir(parents=True, exist_ok=True)
    copy_file(pdf_path, dest_dir / new_name)
    return True


def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("[エラー] ANTHROPIC_API_KEY が設定されていません。.env ファイルを確認してください。")
        input("\nEnter キーで終了...")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    pdf_files = []
    for path in PDF_DIR.rglob("*.pdf"):
        if not any(part in SKIP_FOLDERS for part in path.parts):
            pdf_files.append(path)
    for path in PDF_DIR.rglob("*.PDF"):
        if not any(part in SKIP_FOLDERS for part in path.parts):
            pdf_files.append(path)

    if not pdf_files:
        print(f"PDFファイルが見つかりません: {PDF_DIR}")
        input("\nEnter キーで終了...")
        sys.exit(0)

    print(f"対象ファイル数: {len(pdf_files)}")
    print(f"出力先: {OUT_DIR}\n")

    ok = ng = 0
    for pdf in sorted(set(pdf_files)):
        if process(pdf, client):
            ok += 1
        else:
            ng += 1

    print(f"\n完了: 成功 {ok} 件 / 失敗 {ng} 件")
    print(f"出力フォルダ: {OUT_DIR}")
    input("\nEnter キーで終了...")


if __name__ == "__main__":
    main()
