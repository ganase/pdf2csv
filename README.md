# PDF2CSV — 請求書PDF自動OCR・CSV変換ツール

取引先から受け取った請求書PDF（テキスト型・スキャン型どちらも対応）を、  
Claude AI が自動でOCR・構造化し、BIツールやExcelで即使えるCSVに変換します。

---

## システム構成図

```mermaid
flowchart TD
    User(["👤 ユーザー"])

    subgraph local["ローカル環境"]
        direction TB
        PDFFolder["📁 PDF/\n└ &lt;客先名&gt;/\n　└ invoice.pdf"]
        Script["⚙️ process.py"]
        CSVFolder["📁 CSV/\n└ &lt;客先名&gt;CSV/\n　├ table_definition.csv\n　└ YYYYMMDD_xxx.csv"]
    end

    subgraph ai["Claude AI (Anthropic API)"]
        direction TB
        TextOCR["📄 テキスト抽出\n(pdfplumber)"]
        VisionOCR["🖼️ Vision OCR\n(PyMuPDF + Claude Vision)"]
        Structured["🧠 データ構造化\n(Claude claude-opus-4-6)"]
    end

    subgraph bi["分析ツール"]
        Excel["📊 Excel\nPower Query UNION"]
        BI["📈 BIツール\n(Power BI / Tableau等)"]
    end

    User -->|"PDFを配置"| PDFFolder
    User -->|"python process.py"| Script
    PDFFolder -->|"読み込み"| Script
    Script -->|"テキストPDF"| TextOCR
    Script -->|"スキャンPDF"| VisionOCR
    TextOCR --> Structured
    VisionOCR --> Structured
    Structured -->|"JSON → CSV"| Script
    Script -->|"書き出し"| CSVFolder
    CSVFolder --> Excel
    CSVFolder --> BI
```

---

## フォルダ構成

```
PDF2CSV/              ← リポジトリルート
├── process.py        ← 処理スクリプト（本体）
├── .env.example      ← APIキー設定テンプレート
├── .gitignore
├── README.md
│
├── PDF/              ← ユーザーがPDFを配置するフォルダ（git管理外）
│   └── <客先名>/     ← 客先ごとにフォルダを作成
│       ├── 請求書_2026-03.pdf
│       └── 請求書_2026-04.pdf
│
└── CSV/              ← 自動生成（git管理外）
    └── <客先名>CSV/
        ├── table_definition.csv      ← テーブル定義書（初回自動生成）
        ├── 20260401_請求書_2026-03.csv
        └── 20260415_請求書_2026-04.csv
```

---

## セットアップ手順

### 1. リポジトリのクローン

```bash
git clone https://github.com/ganase/pdf2csv.git
cd pdf2csv
```

### 2. Pythonパッケージのインストール

Python 3.10 以上が必要です。

```bash
pip install pdfplumber pymupdf anthropic python-dotenv pandas
```

### 3. APIキーの設定

`.env.example` をコピーして `.env` を作成し、Anthropic APIキーを入力します。

```bash
# Windows
copy .env.example .env

# Mac / Linux
cp .env.example .env
```

`.env` をテキストエディタで開き、キーを設定：

```
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

> APIキーは https://console.anthropic.com/settings/keys で取得できます。

### 4. PDFフォルダの準備

```
PDF/
└── 株式会社ABC/          ← 客先名でフォルダを作成
    └── 請求書_2026-03.pdf
```

`PDF/` フォルダ内に客先名のサブフォルダを作り、そこにPDFを入れるだけです。

---

## 実行方法

```bash
# 全客先のPDFを処理
python process.py

# 特定の客先のみ処理
python process.py --client 株式会社ABC

# 処理済みファイルも強制再処理
python process.py --force

# フォルダパスを明示的に指定
python process.py --pdf-dir ./PDF --csv-dir ./CSV
```

---

## 処理の流れ

```
process.py 起動
│
├─ PDF/<客先名>/ を走査
│
├─ 各PDFに対して
│   ├─ pdfplumber でテキスト抽出を試みる
│   │   ├─ 成功（テキストPDF）→ Claude API にテキストを送信
│   │   └─ 失敗（スキャンPDF）→ PyMuPDF で2倍解像度PNG化
│   │                            → Claude Vision API に送信
│   │
│   └─ Claude がJSON形式で明細データを返す
│
├─ CSV/<客先名>CSV/ に出力
│   ├─ 初回: table_definition.csv（テーブル定義書）を自動生成
│   └─ 2回目以降: 定義書を参照して同じ列構造で出力
│       └─ 新列が出現した場合: 定義書更新 + 既存CSVにも空列追加
│
└─ 完了
```

---

## 出力CSVの列構成

| 列名 | 内容 | 例 |
|------|------|----|
| `source_file` | 元PDFファイル名 | `請求書_2026-03.pdf` |
| `processed_date` | 処理日 | `2026-04-15` |
| `client_name` | 客先名（フォルダ名） | `株式会社ABC` |
| `billing_month` | 請求月 | `2026-03` |
| `recipient` | 宛先名 | `株式会社XYZ` |
| `item_no` | 明細番号 | `1` |
| `item_description` | 明細項目 | `システム開発費` |
| `quantity` | 数量 | `1` |
| `unit` | 単位 | `式` |
| `unit_price` | 単価 | `500000` |
| `amount` | 金額 | `500000` |
| `tax` | 消費税 | `50000` |
| `subtotal` | 小計 | `500000` |
| `total` | 合計 | `550000` |
| `remarks` | 備考 | `支払期限：2026-04-30` |

> 請求書によって新しい項目が出現した場合、列が自動で追加されます。

---

## BIツール・Excelでの集計

同一客先の全CSVは **同じ列構造** で出力されるため、そのままUNIONできます。

### Excel（Power Query）

1. `データ` タブ → `データの取得` → `ファイルから` → `フォルダーから`
2. `CSV/<客先名>CSV/` フォルダを選択
3. 「バイナリの結合」→ `table_definition.csv` を除外
4. 全CSVが1つのテーブルに結合されます

### Power BI

1. `データを取得` → `フォルダー`
2. `CSV/<客先名>CSV/` を指定
3. `table_definition.csv` をフィルタで除外して読み込み

---

## テーブル定義書（`table_definition.csv`）について

初回処理時に `CSV/<客先名>CSV/table_definition.csv` が自動生成されます。

| column_name | description | example |
|-------------|-------------|---------|
| source_file | 元PDFファイル名 | |
| billing_month | 請求月 (YYYY-MM) | |
| ... | ... | |

- 2回目以降はこの定義書を読み込んで列順を統一します
- 新しい項目が出現した場合、定義書に行を追加し **既存CSVにも空列を追加** します
- `example` 列は手動で記入できます（任意）

---

## 注意事項

- `.env` ファイルは `.gitignore` で管理対象外にしています。APIキーをコミットしないでください
- `PDF/` と `CSV/` フォルダも `.gitignore` で管理対象外です
- スキャンPDFは解像度2倍（144dpi相当）で画像化してOCR精度を高めています
- 同名の出力CSVが既にある場合はスキップします（`--force` で再処理）
- Claude APIの利用料金が発生します（従量課金）

---

## 動作環境

| 項目 | 内容 |
|------|------|
| Python | 3.10 以上 |
| OS | Windows / Mac / Linux |
| API | Anthropic API (Claude claude-opus-4-6) |

## ライセンス

MIT
