#!/bin/bash
cd "$(dirname "$0")"

if ! command -v python3 &>/dev/null; then
    echo "[エラー] python3 が見つかりません。Python をインストールしてください。"
    read -p "Enter キーで終了..."
    exit 1
fi

python3 pdf_rename.py
