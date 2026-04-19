# PDF2CSV — 請求書PDF 自動整理・CSV変換ツール

> **一般ユーザー向けの詳細ガイドは [README.pdf](./README.pdf) をご覧ください。**

---

## できること

取引先から届いたPDF（請求書・注文書など）を所定のフォルダに入れてダブルクリックするだけで、2つの処理を自動実行します。

| 機能 | 説明 | 起動ファイル |
|------|------|-------------|
| **① PDFリネーム・月別整理** | `書類区分_仕入先名_YYYYMM_税込金額.pdf` にリネームして `PDF_RENAMED/<YYYYMM>/` にコピー | `pdf_rename.bat` / `.command` |
| **② PDF → CSV 変換** | 明細行単位でCSV化し、同月の全PDFを `CSV/<YYYYMM>/請求書_YYYYMM.csv` に集約 | `process.bat` / `.command` |

- テキストPDF・スキャン画像PDF どちらも対応
- 書類区分（請求書・注文書・見積書など）を自動判別
- Claude に3回問い合わせて多数決で値を確定（精度向上）
- 失敗ファイルは `失敗_元ファイル名.pdf` として同フォルダに保存
- オリジナルPDFは変更しない

---

## フォルダ構成

```
pdf2csv/
├── PDF/                  # 元ファイル置き場（変更されない）
│   └── 任意のサブフォルダ/
│       └── invoice.pdf
├── PDF_RENAMED/          # リネーム済みコピー（自動生成）
│   └── 202604/
│       └── 請求書_株式会社ABC_202604_110000.pdf
├── CSV/                  # 変換結果（自動生成）
│   └── 202604/
│       └── 請求書_202604.csv
├── pdf_rename.py         # PDFリネーム本体
├── pdf_rename.bat        # Windows 起動用
├── pdf_rename.command    # Mac 起動用
├── process.py            # CSV変換本体
├── process.bat           # Windows 起動用
├── process.command       # Mac 起動用
├── installer.py          # GUIセットアップウィザード（tkinter）
├── setup.bat             # Windows セットアップ起動用
├── requirements.txt      # 依存パッケージ
├── .env.example          # APIキー設定テンプレート
└── README.pdf            # 一般ユーザー向け詳細ガイド（PDF）
```

---

## セットアップ（手動）

```bash
git clone https://github.com/ganase/pdf2csv.git
cd pdf2csv
pip install -r requirements.txt
cp .env.example .env   # Windows: copy .env.example .env
# .env に ANTHROPIC_API_KEY を設定
```

---

## 実行オプション

```bash
# PDFリネーム
python pdf_rename.py

# CSV変換
python process.py
python process.py --force                          # 処理済みも再処理
python process.py --pdf-dir ./PDF --csv-dir ./CSV  # パス明示
```

---

## CSV 出力スキーマ

| 列名 | 内容 |
|------|------|
| 処理日 | 変換実行日 |
| 元ファイル名 | 元のPDFファイル名 |
| 仕入先名 | 発行元の会社名 |
| 請求年月 | YYYY-MM |
| 書類区分 | 請求書・注文書・見積書・納品書・領収書・その他 |
| 明細番号 | 行番号 |
| 品目・摘要 | 明細内容 |
| 数量 / 単位 / 単価 / 金額 / 消費税 | 明細数値 |
| 合計（税込） | 書類全体の税込合計 |
| 備考 | 備考欄 |

---

## 動作環境

| 項目 | 要件 |
|------|------|
| Python | 3.10 以上 |
| OS | Windows / macOS |
| API | Anthropic API（`claude-opus-4-6`） |

---

## ライセンス

MIT
