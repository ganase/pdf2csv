"""
サンプル請求書PDF生成スクリプト
実行すると PDF/samples/ 以下に2種類のサンプルを生成する。

  PDF/samples/テキスト型_株式会社サンプル商事/
      請求書_2026-03.pdf  … テキストが埋め込まれた通常のPDF
      請求書_2026-04.pdf

  PDF/samples/スキャン型_有限会社サンプル工業/
      請求書_2026-03.pdf  … 画像として焼き込んだスキャン相当のPDF
"""

import fitz  # PyMuPDF
from pathlib import Path
from datetime import date

# ============================================================
# 設定
# ============================================================
BASE_DIR    = Path(__file__).parent
SAMPLES_DIR = BASE_DIR / "PDF" / "samples"
FONT_R      = "C:/Windows/Fonts/YuGothR.ttc"   # 游ゴシック Regular
FONT_B      = "C:/Windows/Fonts/YuGothM.ttc"   # 游ゴシック Medium（太字代用）
PAGE_W, PAGE_H = 595, 842   # A4 (pt)


# ============================================================
# ヘルパー
# ============================================================

def _add_fonts(page: fitz.Page) -> None:
    """ページに日本語フォントを登録する。"""
    page.insert_font(fontname="JpR", fontfile=FONT_R)
    page.insert_font(fontname="JpB", fontfile=FONT_B)


def t(page: fitz.Page, x: float, y: float, text: str,
      size: float = 11, bold: bool = False) -> None:
    """テキストをページに挿入する。"""
    page.insert_text((x, y), text,
                     fontname="JpB" if bold else "JpR",
                     fontsize=size)


def hline(page: fitz.Page, y: float, x0: float = 50, x1: float = 545,
          width: float = 0.5) -> None:
    page.draw_line((x0, y), (x1, y), width=width)


# ============================================================
# 請求書ページを描画（テキスト型）
# ============================================================

def build_invoice_page(
    doc: fitz.Document,
    billing_month: str,    # "2026-03"
    recipient: str,
    issuer: str,
    items: list[dict],     # [{desc, qty, unit, unit_price}]
    remarks: str = "",
) -> None:
    page = doc.new_page(width=PAGE_W, height=PAGE_H)
    _add_fonts(page)

    year, month = billing_month.split("-")

    # ── タイトル ──────────────────────────────────────────
    t(page, 220, 60, "請　求　書", size=22, bold=True)
    hline(page, 75, width=1.0)

    # ── 請求月・発行日 ─────────────────────────────────────
    t(page, 50, 100, f"請求月：{year}年{month}月分")
    t(page, 380, 100, f"発行日：{date.today().strftime('%Y年%m月%d日')}", size=10)

    # ── 宛先 ──────────────────────────────────────────────
    t(page, 50, 135, f"{recipient}　御中", size=14, bold=True)
    hline(page, 150, x0=50, x1=300)

    # ── 発行者情報 ─────────────────────────────────────────
    t(page, 360, 130, issuer, size=10)
    t(page, 360, 145, "〒100-0001　東京都千代田区丸の内1-1-1", size=9)
    t(page, 360, 158, "TEL: 03-0000-0000", size=9)

    # ── 合計金額ボックス ───────────────────────────────────
    subtotal = sum(d["qty"] * d["unit_price"] for d in items)
    tax      = int(subtotal * 0.10)
    total    = subtotal + tax

    t(page, 50, 185, "下記の通りご請求申し上げます。")
    box = fitz.Rect(50, 195, 340, 228)
    page.draw_rect(box, width=1.0)
    t(page, 58, 210, "ご請求金額（税込）", size=10)
    t(page, 170, 219, f"¥ {total:,}", size=16, bold=True)

    # ── 明細テーブル ──────────────────────────────────────
    table_top = 248
    # 列の左端X座標: No / 品目 / 数量 / 単位 / 単価 / 金額
    col_x     = [50, 240, 330, 375, 445, 498]
    headers   = ["No", "品目・摘要", "数量", "単位", "単価", "金額"]
    row_h     = 20

    # ヘッダー行の背景・枠
    page.draw_rect(fitz.Rect(50, table_top, 545, table_top + row_h), width=0.5)
    for i, h in enumerate(headers):
        t(page, col_x[i] + 3, table_top + 14, h, size=9, bold=True)

    # 縦線（ヘッダー＋データ行）
    n_rows = len(items)
    for cx in col_x[1:]:
        page.draw_line(
            (cx, table_top),
            (cx, table_top + row_h * (n_rows + 1)),
            width=0.4,
        )

    # データ行
    for ri, item in enumerate(items):
        ry  = table_top + row_h + ri * row_h
        amt = item["qty"] * item["unit_price"]
        page.draw_rect(fitz.Rect(50, ry, 545, ry + row_h), width=0.3)
        for i, v in enumerate([
            str(ri + 1),
            item["desc"],
            str(item["qty"]),
            item["unit"],
            f"{item['unit_price']:,}",
            f"{amt:,}",
        ]):
            t(page, col_x[i] + 3, ry + 14, v, size=9)

    # ── 小計・税・合計 ────────────────────────────────────
    sy = table_top + row_h * (n_rows + 1) + 18
    for label, value, bold in [
        ("小計",         subtotal, False),
        ("消費税（10%）", tax,     False),
        ("合計（税込）",  total,   True),
    ]:
        t(page, 365, sy, label, size=10, bold=bold)
        t(page, 470, sy, f"¥ {value:,}", size=10, bold=bold)
        hline(page, sy + 5, x0=355, x1=545, width=0.3)
        sy += 22

    # ── 備考 ──────────────────────────────────────────────
    if remarks:
        t(page, 50, sy + 12, f"備考：{remarks}", size=9)

    # ── 振込先 ────────────────────────────────────────────
    bank_y = PAGE_H - 100
    hline(page, bank_y - 10)
    t(page, 50, bank_y,      "【お振込先】", size=10, bold=True)
    t(page, 50, bank_y + 16, "サンプル銀行　丸の内支店　普通　1234567", size=10)
    t(page, 50, bank_y + 32, f"口座名義：{issuer}", size=10)
    t(page, 50, bank_y + 50,
      "※ お振込手数料はご負担いただきますようお願いいたします。", size=9)


# ============================================================
# スキャン型PDF（テキストPDF→ラスタライズ→画像PDF）
# ============================================================

def make_scanned_pdf(src: Path, dst: Path) -> None:
    src_doc = fitz.open(str(src))
    dst_doc = fitz.open()
    for page in src_doc:
        pix      = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
        new_page = dst_doc.new_page(width=page.rect.width, height=page.rect.height)
        new_page.insert_image(new_page.rect, pixmap=pix)
    src_doc.close()
    dst_doc.save(str(dst))
    dst_doc.close()


# ============================================================
# メイン
# ============================================================

def main():
    # ── サンプルデータ ─────────────────────────────────────

    # 客先1: テキスト型（2ヶ月分）
    client_text = "テキスト型_株式会社サンプル商事"
    invoices_text = [
        {
            "billing_month": "2026-03",
            "recipient": "株式会社テスト物産",
            "issuer":    "株式会社サンプル商事",
            "items": [
                {"desc": "Webシステム開発費（3月分）",   "qty":  1, "unit": "式",   "unit_price": 500000},
                {"desc": "サーバー保守管理費",            "qty":  1, "unit": "月",   "unit_price":  50000},
                {"desc": "追加機能開発（ログイン画面）",  "qty":  8, "unit": "時間", "unit_price":  12500},
            ],
            "remarks": "お支払期限：2026年4月30日",
        },
        {
            "billing_month": "2026-04",
            "recipient": "株式会社テスト物産",
            "issuer":    "株式会社サンプル商事",
            "items": [
                {"desc": "Webシステム開発費（4月分）",   "qty":  1, "unit": "式",   "unit_price": 500000},
                {"desc": "サーバー保守管理費",            "qty":  1, "unit": "月",   "unit_price":  50000},
                {"desc": "データ移行作業",                "qty": 12, "unit": "時間", "unit_price":  12500},
                {"desc": "ソフトウェアライセンス費",      "qty":  5, "unit": "本",   "unit_price":  15000},
            ],
            "remarks": "お支払期限：2026年5月31日",
        },
    ]

    # 客先2: スキャン型（1ヶ月分）
    client_scan = "スキャン型_有限会社サンプル工業"
    invoices_scan = [
        {
            "billing_month": "2026-03",
            "recipient": "株式会社テスト物産",
            "issuer":    "有限会社サンプル工業",
            "items": [
                {"desc": "製造委託費（部品A）", "qty": 100, "unit": "個", "unit_price":  1500},
                {"desc": "製造委託費（部品B）", "qty":  50, "unit": "個", "unit_price":  3200},
                {"desc": "梱包・発送手数料",    "qty":   1, "unit": "式", "unit_price":  8000},
            ],
            "remarks": "納品書No.20260315-001　お支払期限：2026年4月30日",
        },
    ]

    # ── テキスト型を生成 ───────────────────────────────────
    out_dir = SAMPLES_DIR / client_text
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"[テキスト型] {out_dir}")
    for inv in invoices_text:
        doc  = fitz.open()
        build_invoice_page(doc, **inv)
        fname = f"請求書_{inv['billing_month']}.pdf"
        doc.save(str(out_dir / fname))
        doc.close()
        print(f"  生成: {fname}")

    # ── スキャン型を生成（テキスト→画像化） ──────────────
    out_dir_scan = SAMPLES_DIR / client_scan
    out_dir_scan.mkdir(parents=True, exist_ok=True)
    tmp_dir = SAMPLES_DIR / "_tmp"
    tmp_dir.mkdir(exist_ok=True)
    print(f"[スキャン型] {out_dir_scan}")
    for inv in invoices_scan:
        fname     = f"請求書_{inv['billing_month']}.pdf"
        tmp_path  = tmp_dir / fname
        out_path  = out_dir_scan / fname

        doc = fitz.open()
        build_invoice_page(doc, **inv)
        doc.save(str(tmp_path))
        doc.close()

        make_scanned_pdf(tmp_path, out_path)
        tmp_path.unlink()
        print(f"  生成（スキャン型）: {fname}")

    tmp_dir.rmdir()

    print("\nサンプルPDFの生成が完了しました。")
    print(f"格納先: {SAMPLES_DIR}")
    print("\n次のコマンドで変換を試せます:")
    print(f"  python process.py --client \"{client_text}\"")
    print(f"  python process.py --client \"{client_scan}\"")


if __name__ == "__main__":
    main()
