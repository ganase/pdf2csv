# PDF2CSV — 請求書PDF 自動整理・CSV変換ツール

> **詳細ガイドは [README.pdf](./README.pdf) をご覧ください。**

---

## 初期セットアップ

### 1. ZIPを展開する

GitHubのリポジトリページから **Code → Download ZIP** でダウンロードし、任意のフォルダに展開します。

```
pdf2csv-main/   ← 展開後のフォルダ名（任意の場所でOK）
```

### 2. Python をインストールする

Python 3.10 以上が必要です。インストール済みの場合はスキップ。

- [https://www.python.org/downloads/](https://www.python.org/downloads/) からダウンロード
- インストール時に **「Add Python to PATH」にチェック**を入れること

### 3. 依存パッケージをインストールする

展開したフォルダ内でコマンドプロンプト（またはターミナル）を開き、次のコマンドを実行します。

```cmd
pip install -r requirements.txt
```

### 4. APIキーを設定する

`.env.example` を `.env` にコピーし、Rakuten AI Gateway のAPIキーを設定します。

**Windows:**
```cmd
copy .env.example .env
```

`.env` をテキストエディタで開き、次のように編集します。

```
RAKUTEN_AI_GATEWAY_KEY=your_api_key_here
```

> APIキーはブラウザUI の設定画面からも設定できます（手順5以降）。

### 5. Web UI を起動する

`web.bat`（Windows）または `web.command`（Mac）をダブルクリックします。

ブラウザが自動で開き、`http://localhost:8000` にアクセスされます。

### 6. APIキーを画面から設定する（手順4をスキップした場合）

右上の **設定ボタン（歯車）** をクリックし、Rakuten AI Gateway キーを入力して保存します。

---

## できること

取引先から届いたPDF（請求書・注文書など）を `PDF/` フォルダに置き、ブラウザUIから操作するだけで2つの処理を自動実行します。

| 機能 | 説明 |
|------|------|
| **PDFリネーム・月別整理** | `書類区分_仕入先名_YYYYMM_税込金額.pdf` にリネームして `PDF_RENAMED/<YYYYMM>/` にコピー |
| **PDF → CSV 変換** | 明細行単位でCSV化し、同月の全PDFを `CSV/<YYYYMM>/書類_YYYYMM.csv` に集約 |

- テキストPDF・スキャン画像PDF どちらも対応
- 書類区分（請求書・注文書・見積書など）を自動判別
- 複数LLMモデル対応（Anthropic / OpenAI / Gemini / Rakuten AI）
- LLMに3回問い合わせて多数決で値を確定（精度向上）
- 失敗ファイルは `失敗_元ファイル名.pdf` として保存
- オリジナルPDFは変更しない

---

## フォルダ構成

```
pdf2csv/
├── PDF/                  # 元ファイル置き場（変更されない）
│   └── samples/          # サンプルPDF
├── PDF_RENAMED/          # リネーム済みコピー（自動生成）
│   └── 202604/
├── PDF_ARCHIVE/          # アーカイブ済みPDF（自動生成）
├── CSV/                  # 変換結果（自動生成）
│   └── 202604/
│       └── 書類_202604.csv
├── app/                  # Web UI バックエンド（FastAPI）
│   ├── main.py
│   └── services/
│       ├── claude.py         # LLM呼び出し統一層
│       ├── pdf_rename_svc.py
│       └── pdf_process_svc.py
├── static/
│   └── index.html        # Web UI フロントエンド
├── web.bat               # Windows 起動用
├── web.command           # Mac 起動用
├── requirements.txt
├── .env.example
├── Dockerfile
├── render.yaml           # Render デプロイ設定
└── README.pdf            # 詳細ガイド（PDF）
```

---

## 使い方（ブラウザUI）

1. `web.bat` をダブルクリックしてサーバーを起動
2. ブラウザで `http://localhost:8000` を開く
3. PDFをアップロード、または `PDF/` フォルダに直接配置
4. タブで **CSV変換** または **PDFリネーム** を選択
5. 対象ファイルにチェックを入れて実行ボタンをクリック
6. 処理完了後、結果画面からCSV/PDFをダウンロード

### フォルダボタン

- **PDF ボタン**: `PDF/` フォルダをエクスプローラーで開く
- **CSV ボタン**: `CSV/` フォルダをエクスプローラーで開く

### Archive ボタン

選択したPDFを `PDF_ARCHIVE/` フォルダへ移動します（処理済みファイルの整理に）。

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

## 対応LLMモデル

設定画面からプロバイダーとモデルを選択できます。リストにないモデルIDは手入力も可能です。

| プロバイダー | 主なモデル |
|---|---|
| Rakuten Gateway (Anthropic) | claude-sonnet-4-6, claude-haiku-4-5 |
| Rakuten Gateway (OpenAI) | gpt-5.1, gpt-5-mini など |
| Rakuten Gateway (Gemini) | gemini-3-flash-preview など |
| Rakuten AI | rakutenai-2.0, rakutenai-3.0 など |

---

## 動作環境

| 項目 | 要件 |
|------|------|
| Python | 3.10 以上 |
| OS | Windows / macOS |
| API | Rakuten AI Gateway |

---

## クラウドデプロイ（Render）

`render.yaml` を使って Render 無料プランにデプロイできます。
環境変数 `RAKUTEN_AI_GATEWAY_KEY` を Render の管理画面で設定してください。

---

## ライセンス

MIT
