"""
PDF2CSV インストーラー
GUIウィザード形式でセットアップを行う。

実行方法: python installer.py
"""

import os
import sys
import subprocess
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path


# ============================================================
# 定数
# ============================================================
APP_TITLE = "PDF2CSV セットアップウィザード"
WINDOW_WIDTH = 580
WINDOW_HEIGHT = 520

REQUIRED_PACKAGES = [
    "pdfplumber",
    "pymupdf",
    "anthropic",
    "python-dotenv",
    "pandas",
]

STEPS = [
    "ようこそ",
    "Pythonの確認",
    "パッケージインストール",
    "APIキーの設定",
    "フォルダの設定",
    "セットアップ完了",
]


# ============================================================
# ウィザードアプリ本体
# ============================================================
class InstallerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.resizable(False, False)

        # ウィンドウを画面中央に配置
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = (sw - WINDOW_WIDTH) // 2
        y = (sh - WINDOW_HEIGHT) // 2
        self.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}+{x}+{y}")

        self.current_step = 0
        self.install_dir = tk.StringVar(value=str(Path(__file__).parent.resolve()))
        self.api_key = tk.StringVar()
        self.api_key_visible = tk.BooleanVar(value=False)

        self._build_ui()
        self._show_step(0)

    # ----------------------------------------------------------
    # UI 骨格
    # ----------------------------------------------------------
    def _build_ui(self):
        # ヘッダー（タイトルバー）
        header = tk.Frame(self, bg="#1a1a2e", height=70)
        header.pack(fill="x")
        header.pack_propagate(False)

        self.header_title = tk.Label(
            header, text=APP_TITLE,
            bg="#1a1a2e", fg="white",
            font=("Yu Gothic UI", 14, "bold"),
        )
        self.header_title.place(relx=0.04, rely=0.5, anchor="w")

        self.header_sub = tk.Label(
            header, text="",
            bg="#1a1a2e", fg="#a0a0c0",
            font=("Yu Gothic UI", 9),
        )
        self.header_sub.place(relx=0.04, rely=0.78, anchor="w")

        # ボトムバー ── side="bottom" は他より先に pack しないと押し出される
        bottom = tk.Frame(self, bg="#e8e8f0", pady=10, padx=20)
        bottom.pack(fill="x", side="bottom")

        self.btn_back = ttk.Button(bottom, text="< 戻る", command=self._go_back, width=10)
        self.btn_back.pack(side="left")

        self.btn_next = ttk.Button(bottom, text="次へ >", command=self._go_next, width=10)
        self.btn_next.pack(side="right")

        self.btn_cancel = ttk.Button(bottom, text="キャンセル", command=self._on_cancel, width=10)
        self.btn_cancel.pack(side="right", padx=8)

        # ステップインジケーター
        indicator_frame = tk.Frame(self, bg="#f0f0f5", pady=6)
        indicator_frame.pack(fill="x")
        self.step_labels = []
        for i, name in enumerate(STEPS):
            lbl = tk.Label(
                indicator_frame, text=f"{i+1}",
                font=("Yu Gothic UI", 8),
                width=3, height=1,
                relief="flat",
            )
            lbl.pack(side="left", padx=4)
            self.step_labels.append(lbl)

        # コンテンツエリア
        self.content = tk.Frame(self, bg="white", padx=32, pady=16)
        self.content.pack(fill="both", expand=True)

    # ----------------------------------------------------------
    # ステップ切り替え
    # ----------------------------------------------------------
    def _show_step(self, step: int):
        self.current_step = step

        # ステップインジケーター更新
        for i, lbl in enumerate(self.step_labels):
            if i < step:
                lbl.configure(bg="#4caf50", fg="white")       # 完了
            elif i == step:
                lbl.configure(bg="#1a1a2e", fg="white")       # 現在
            else:
                lbl.configure(bg="#ccccdd", fg="#666666")     # 未来

        # コンテンツをクリア
        for w in self.content.winfo_children():
            w.destroy()

        # ヘッダー更新
        self.header_sub.configure(text=f"ステップ {step+1} / {len(STEPS)}  —  {STEPS[step]}")

        # ボタン状態
        self.btn_back.configure(state="normal" if step > 0 else "disabled")
        self.btn_next.configure(text="完了" if step == len(STEPS) - 1 else "次へ  ▶")
        self.btn_cancel.configure(state="normal" if step < len(STEPS) - 1 else "disabled")

        # ページ描画
        pages = [
            self._page_welcome,
            self._page_python_check,
            self._page_packages,
            self._page_apikey,
            self._page_folders,
            self._page_done,
        ]
        pages[step]()

    def _go_next(self):
        if not self._validate_current():
            return
        if self.current_step < len(STEPS) - 1:
            self._show_step(self.current_step + 1)
        else:
            self.destroy()

    def _go_back(self):
        if self.current_step > 0:
            self._show_step(self.current_step - 1)

    def _on_cancel(self):
        if messagebox.askyesno("キャンセル", "セットアップを中止しますか？"):
            self.destroy()

    # ----------------------------------------------------------
    # バリデーション
    # ----------------------------------------------------------
    def _validate_current(self) -> bool:
        if self.current_step == 3:   # APIキー
            key = self.api_key.get().strip()
            if not key:
                messagebox.showwarning("入力エラー", "Anthropic APIキーを入力してください。")
                return False
            if not key.startswith("sk-ant-"):
                if not messagebox.askyesno(
                    "確認",
                    "入力されたキーが 'sk-ant-' で始まっていません。\nこのまま続けますか？",
                ):
                    return False
        if self.current_step == 4:   # フォルダ
            d = Path(self.install_dir.get())
            if not d.exists():
                messagebox.showwarning("入力エラー", f"フォルダが存在しません:\n{d}")
                return False
            # .env 書き出し
            self._write_env(d)
            # PDF / CSV フォルダ作成
            (d / "PDF").mkdir(exist_ok=True)
            (d / "CSV").mkdir(exist_ok=True)
        return True

    # ----------------------------------------------------------
    # ページ: ようこそ
    # ----------------------------------------------------------
    def _page_welcome(self):
        c = self.content
        tk.Label(c, text="PDF2CSV へようこそ", font=("Yu Gothic UI", 16, "bold"),
                 bg="white").pack(anchor="w", pady=(0, 12))

        msg = (
            "このウィザードは PDF2CSV のセットアップを自動で行います。\n\n"
            "【このツールでできること】\n"
            "  • 取引先から受け取った請求書PDF（テキスト型・スキャン型）を\n"
            "    自動でOCRし、CSV形式に変換します。\n"
            "  • 客先ごとにフォルダを分けてデータを管理します。\n"
            "  • ExcelやBIツールでそのままUNION集計できます。\n\n"
            "【セットアップの流れ】\n"
            "  1. Python環境の確認\n"
            "  2. 必要パッケージのインストール\n"
            "  3. Anthropic APIキーの設定\n"
            "  4. 作業フォルダの確認\n\n"
            "「次へ」をクリックして開始してください。"
        )
        tk.Label(c, text=msg, font=("Yu Gothic UI", 10), bg="white",
                 justify="left", wraplength=480).pack(anchor="w")

    # ----------------------------------------------------------
    # ページ: Python確認
    # ----------------------------------------------------------
    def _page_python_check(self):
        c = self.content
        tk.Label(c, text="Python 環境の確認", font=("Yu Gothic UI", 14, "bold"),
                 bg="white").pack(anchor="w", pady=(0, 16))

        version = sys.version
        major, minor = sys.version_info.major, sys.version_info.minor
        ok = major >= 3 and minor >= 10

        # バージョン表示
        frame = tk.Frame(c, bg="#f5f5fa", relief="flat", bd=1)
        frame.pack(fill="x", pady=4)
        tk.Label(frame, text=f"Python バージョン:  {version}",
                 font=("Consolas", 10), bg="#f5f5fa", padx=12, pady=10,
                 justify="left").pack(anchor="w")

        # 判定
        if ok:
            icon, color, msg = "✅", "#2e7d32", "Python 3.10 以上が確認できました。このまま続けられます。"
        else:
            icon, color, msg = "❌", "#c62828", (
                f"Python {major}.{minor} は対応バージョン外です。\n"
                "Python 3.10 以上をインストールしてから再実行してください。\n"
                "https://www.python.org/downloads/"
            )

        tk.Label(c, text=f"{icon}  {msg}", font=("Yu Gothic UI", 10),
                 bg="white", fg=color, wraplength=480, justify="left").pack(anchor="w", pady=12)

        if not ok:
            self.btn_next.configure(state="disabled")

        tk.Label(c, text=f"実行ファイル:  {sys.executable}",
                 font=("Consolas", 9), bg="white", fg="#666").pack(anchor="w", pady=(8, 0))

    # ----------------------------------------------------------
    # ページ: パッケージインストール
    # ----------------------------------------------------------
    def _page_packages(self):
        c = self.content
        tk.Label(c, text="必要パッケージのインストール", font=("Yu Gothic UI", 14, "bold"),
                 bg="white").pack(anchor="w", pady=(0, 8))
        tk.Label(c, text="以下のパッケージをインストールします。「インストール」ボタンを押してください。",
                 font=("Yu Gothic UI", 10), bg="white", wraplength=480).pack(anchor="w", pady=(0, 10))

        # パッケージリスト
        list_frame = tk.Frame(c, bg="#f5f5fa", relief="flat", bd=1)
        list_frame.pack(fill="x")
        for pkg in REQUIRED_PACKAGES:
            tk.Label(list_frame, text=f"  • {pkg}",
                     font=("Consolas", 10), bg="#f5f5fa", anchor="w").pack(fill="x", pady=1)

        # ログエリア
        self.pkg_log = tk.Text(c, height=6, font=("Consolas", 9),
                               bg="#1e1e1e", fg="#d4d4d4",
                               relief="flat", state="disabled")
        self.pkg_log.pack(fill="x", pady=(10, 0))

        # プログレスバー
        self.pkg_progress = ttk.Progressbar(c, mode="indeterminate", length=480)
        self.pkg_progress.pack(pady=(6, 0))

        # インストールボタン
        self.btn_install = ttk.Button(c, text="インストール開始", command=self._run_install)
        self.btn_install.pack(pady=(8, 0))

        self.btn_next.configure(state="disabled")

    def _run_install(self):
        self.btn_install.configure(state="disabled")
        self.btn_back.configure(state="disabled")
        self.pkg_progress.start(12)

        def worker():
            self._log_append(">>> pip install を開始します...\n")
            cmd = [sys.executable, "-m", "pip", "install", "--upgrade"] + REQUIRED_PACKAGES
            try:
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )
                for line in proc.stdout:
                    self._log_append(line)
                proc.wait()
                if proc.returncode == 0:
                    self._log_append("\n✅ インストール完了。\n")
                    self.after(0, lambda: self.btn_next.configure(state="normal"))
                else:
                    self._log_append(f"\n❌ エラーが発生しました (code={proc.returncode})。\n")
            except Exception as e:
                self._log_append(f"\n❌ 例外: {e}\n")
            finally:
                self.after(0, self.pkg_progress.stop)
                self.after(0, lambda: self.btn_back.configure(state="normal"))

        threading.Thread(target=worker, daemon=True).start()

    def _log_append(self, text: str):
        def _do():
            self.pkg_log.configure(state="normal")
            self.pkg_log.insert("end", text)
            self.pkg_log.see("end")
            self.pkg_log.configure(state="disabled")
        self.after(0, _do)

    # ----------------------------------------------------------
    # ページ: APIキー設定
    # ----------------------------------------------------------
    def _page_apikey(self):
        c = self.content
        tk.Label(c, text="Anthropic APIキーの設定", font=("Yu Gothic UI", 14, "bold"),
                 bg="white").pack(anchor="w", pady=(0, 6))

        tk.Label(
            c,
            text=(
                "PDF2CSV は Claude AI（Anthropic社）のAPIを使用します。\n"
                "APIキーを取得して以下に貼り付けてください。"
            ),
            font=("Yu Gothic UI", 10), bg="white", justify="left",
        ).pack(anchor="w", pady=(0, 10))

        # 取得リンク案内
        link_frame = tk.Frame(c, bg="#e8f4fd", relief="flat", bd=1)
        link_frame.pack(fill="x", pady=(0, 14))
        tk.Label(
            link_frame,
            text="  🔑  https://console.anthropic.com/settings/keys",
            font=("Consolas", 10), bg="#e8f4fd", fg="#0066cc", pady=8,
        ).pack(anchor="w")

        # 入力フィールド
        tk.Label(c, text="APIキー:", font=("Yu Gothic UI", 10, "bold"),
                 bg="white").pack(anchor="w")

        entry_frame = tk.Frame(c, bg="white")
        entry_frame.pack(fill="x", pady=(4, 0))

        self._api_entry = tk.Entry(
            entry_frame, textvariable=self.api_key,
            font=("Consolas", 11), show="•", width=46,
            relief="solid", bd=1,
        )
        self._api_entry.pack(side="left", ipady=5)

        def toggle_visibility():
            if self.api_key_visible.get():
                self._api_entry.configure(show="")
                btn_eye.configure(text="🙈")
            else:
                self._api_entry.configure(show="•")
                btn_eye.configure(text="👁")
            self.api_key_visible.set(not self.api_key_visible.get())

        btn_eye = tk.Button(entry_frame, text="👁", command=toggle_visibility,
                            font=("", 12), relief="flat", bg="white", cursor="hand2")
        btn_eye.pack(side="left", padx=6)

        tk.Label(
            c,
            text="※ APIキーは .env ファイルに保存されます。GitHubには公開されません。",
            font=("Yu Gothic UI", 9), bg="white", fg="#888",
        ).pack(anchor="w", pady=(10, 0))

        # 課金案内
        tk.Label(
            c,
            text="※ Claude APIは従量課金です。請求書1件あたり数円〜数十円程度が目安です。",
            font=("Yu Gothic UI", 9), bg="white", fg="#888",
        ).pack(anchor="w", pady=(4, 0))

    # ----------------------------------------------------------
    # ページ: フォルダ設定
    # ----------------------------------------------------------
    def _page_folders(self):
        c = self.content
        tk.Label(c, text="作業フォルダの確認", font=("Yu Gothic UI", 14, "bold"),
                 bg="white").pack(anchor="w", pady=(0, 6))

        tk.Label(
            c,
            text=(
                "PDF と CSV の作業フォルダを設定します。\n"
                "デフォルトはスクリプトと同じ場所です。変更する場合は「参照」で選んでください。"
            ),
            font=("Yu Gothic UI", 10), bg="white", justify="left",
        ).pack(anchor="w", pady=(0, 14))

        # インストール先
        tk.Label(c, text="作業フォルダ:", font=("Yu Gothic UI", 10, "bold"),
                 bg="white").pack(anchor="w")
        dir_frame = tk.Frame(c, bg="white")
        dir_frame.pack(fill="x", pady=(4, 0))

        tk.Entry(dir_frame, textvariable=self.install_dir,
                 font=("Consolas", 10), width=44, relief="solid", bd=1).pack(side="left", ipady=4)
        ttk.Button(dir_frame, text="参照…", width=7,
                   command=self._browse_dir).pack(side="left", padx=6)

        # 作成されるフォルダ
        preview_frame = tk.Frame(c, bg="#f5f5fa", relief="flat", bd=1)
        preview_frame.pack(fill="x", pady=(16, 0))
        tk.Label(preview_frame, text="作成されるフォルダ構成:",
                 font=("Yu Gothic UI", 9, "bold"), bg="#f5f5fa", padx=12, pady=6).pack(anchor="w")
        preview_text = (
            "  <作業フォルダ>/\n"
            "  ├── PDF/               ← 客先フォルダとPDFをここに入れる\n"
            "  ├── CSV/               ← 変換済みCSVが自動生成される\n"
            "  └── .env               ← APIキーが保存される（非公開）"
        )
        tk.Label(preview_frame, text=preview_text,
                 font=("Consolas", 9), bg="#f5f5fa", justify="left",
                 padx=12, pady=4).pack(anchor="w")

        tk.Label(
            c,
            text="「次へ」を押すと .env の書き込みと PDF/CSV フォルダの作成が行われます。",
            font=("Yu Gothic UI", 9), bg="white", fg="#555",
        ).pack(anchor="w", pady=(12, 0))

    def _browse_dir(self):
        d = filedialog.askdirectory(initialdir=self.install_dir.get(), title="作業フォルダを選択")
        if d:
            self.install_dir.set(d)

    # ----------------------------------------------------------
    # ページ: 完了
    # ----------------------------------------------------------
    def _page_done(self):
        c = self.content
        tk.Label(c, text="セットアップ完了！", font=("Yu Gothic UI", 18, "bold"),
                 bg="white", fg="#2e7d32").pack(pady=(10, 12))

        install_path = Path(self.install_dir.get())

        msg = (
            f"PDF2CSV のセットアップが完了しました。\n\n"
            f"作業フォルダ:\n  {install_path}\n\n"
            "【次のステップ】\n\n"
            "  1. PDF フォルダに客先名のサブフォルダを作成する\n"
            "       例: PDF\\株式会社ABC\\\n\n"
            "  2. そのフォルダに請求書PDFを入れる\n\n"
            "  3. 以下のコマンドで処理を実行する:\n"
            f"       cd \"{install_path}\"\n"
            "       python process.py\n\n"
            "  4. CSV\\<客先名>CSV\\ に変換済みCSVが生成される"
        )
        tk.Label(c, text=msg, font=("Yu Gothic UI", 10), bg="white",
                 justify="left", wraplength=490).pack(anchor="w")

        def open_folder():
            os.startfile(str(install_path))

        ttk.Button(c, text="📁  作業フォルダを開く", command=open_folder).pack(pady=(12, 0))

    # ----------------------------------------------------------
    # .env 書き出し
    # ----------------------------------------------------------
    def _write_env(self, directory: Path):
        env_path = directory / ".env"
        with open(env_path, "w", encoding="utf-8") as f:
            f.write(f"ANTHROPIC_API_KEY={self.api_key.get().strip()}\n")


# ============================================================
# エントリポイント
# ============================================================
if __name__ == "__main__":
    app = InstallerApp()
    app.mainloop()
