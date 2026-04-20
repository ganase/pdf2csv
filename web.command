#!/bin/bash
cd "$(dirname "$0")"

if ! command -v python3 &>/dev/null; then
    echo "Python3 が見つかりません。インストールしてください。"
    read -p "Enter キーで終了..."
    exit 1
fi

pip3 show uvicorn &>/dev/null || pip3 install "fastapi>=0.111.0" "uvicorn[standard]>=0.29.0" "python-multipart>=0.0.9"

echo "PDF2CSV Web UI を起動します: http://localhost:8000"
sleep 2 && open http://localhost:8000 &
python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
