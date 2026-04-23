"""
PDF2CSV Web UI — FastAPI バックエンド
"""

import asyncio
import os
import re
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv, dotenv_values
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .services.claude import FatalApiError, make_client, PROVIDERS, DEFAULT_PROVIDER
from .services.pdf_rename_svc import rename_one
from .services.pdf_process_svc import process_one

# ── パス設定 ──────────────────────────────────────────────────
BASE_DIR     = Path(__file__).parent.parent
ENV_PATH     = BASE_DIR / ".env"

# Render などクラウドでは /app/data 以下を永続ディスクとして使う
if os.environ.get("RENDER") or os.environ.get("USE_DATA_DIR"):
    DATA_DIR    = Path("/app/data")
    PDF_DIR     = DATA_DIR / "PDF"
    RENAMED_DIR = DATA_DIR / "PDF_RENAMED"
    CSV_DIR     = DATA_DIR / "CSV"
    ARCHIVE_DIR = DATA_DIR / "PDF_ARCHIVE"
else:
    PDF_DIR     = BASE_DIR / "PDF"
    RENAMED_DIR = BASE_DIR / "PDF_RENAMED"
    CSV_DIR     = BASE_DIR / "CSV"
    ARCHIVE_DIR = BASE_DIR / "PDF_ARCHIVE"

SKIP_DIRS = {"samples"}

# ── アプリ初期化 ──────────────────────────────────────────────
app = FastAPI(title="PDF2CSV Web UI")

# static/ をマウント（index.html はルートで別途配信）
STATIC_DIR = BASE_DIR / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# ── ジョブストア & イベントループ参照 ─────────────────────────
jobs: dict[str, dict] = {}
_loop: asyncio.AbstractEventLoop | None = None
_executor = ThreadPoolExecutor(max_workers=4)


@app.on_event("startup")
async def _startup():
    global _loop
    _loop = asyncio.get_running_loop()
    for d in (PDF_DIR, RENAMED_DIR, CSV_DIR, ARCHIVE_DIR):
        d.mkdir(parents=True, exist_ok=True)


# ── ルート ─────────────────────────────────────────────────────
@app.get("/", include_in_schema=False)
async def index():
    return FileResponse(
        str(STATIC_DIR / "index.html"),
        headers={"Cache-Control": "no-store"},
    )


# ── プロバイダー別 env var 名マッピング ────────────────────────
_PROVIDER_ENV_VARS = {
    "rakuten_anthropic": "RAKUTEN_AI_GATEWAY_KEY",
    "rakuten_openai":    "RAKUTEN_AI_GATEWAY_KEY",
    "rakuten_gemini":    "RAKUTEN_AI_GATEWAY_KEY",
    "rakuten_llm":       "RAKUTEN_AI_GATEWAY_KEY",
    "openai":            "OPENAI_API_KEY",
    "anthropic":         "ANTHROPIC_API_KEY",
}

def _env_var_for(provider: str) -> str:
    return _PROVIDER_ENV_VARS.get(provider, "RAKUTEN_AI_GATEWAY_KEY")

def _get_api_key(provider: str) -> str:
    load_dotenv(str(ENV_PATH), override=True)
    return os.environ.get(_env_var_for(provider), "")

def _saved_provider() -> str:
    """前回保存したプロバイダーを .env から読む。なければ DEFAULT_PROVIDER。"""
    return dotenv_values(str(ENV_PATH)).get("LAST_PROVIDER", DEFAULT_PROVIDER)


# ── 設定 ──────────────────────────────────────────────────────
@app.get("/api/settings")
async def get_settings(provider: str | None = None):
    # provider 未指定なら前回保存値を使う
    if not provider:
        provider = _saved_provider()
    env_var = _env_var_for(provider)
    load_dotenv(str(ENV_PATH), override=True)
    env_key = os.environ.get(env_var, "")
    if env_key:
        return {"api_key_set": True, "api_key_masked": _mask(env_key),
                "source": "env_var", "env_var": env_var, "last_provider": provider}
    dotenv_key = dotenv_values(str(ENV_PATH)).get(env_var, "")
    if dotenv_key:
        return {"api_key_set": True, "api_key_masked": _mask(dotenv_key),
                "source": "dotenv", "env_var": env_var, "last_provider": provider}
    return {"api_key_set": False, "api_key_masked": "",
            "source": "dotenv", "env_var": env_var, "last_provider": provider}


class SettingsBody(BaseModel):
    api_key: str
    provider: str = DEFAULT_PROVIDER


@app.post("/api/settings")
async def post_settings(body: SettingsBody):
    env_var = _env_var_for(body.provider)
    if os.environ.get(env_var):
        raise HTTPException(400, "環境変数で設定されているため変更できません")
    key = body.api_key.strip()
    if not key:
        raise HTTPException(422, "APIキーが空です")
    _write_env_key(env_var, key)
    _write_env_key("LAST_PROVIDER", body.provider)
    return {"ok": True}


class ModelBody(BaseModel):
    provider: str
    model: str = ""


@app.post("/api/settings/model")
async def post_model_settings(body: ModelBody):
    """プロバイダー・モデル選択のみ保存（APIキー変更なし）"""
    _write_env_key("LAST_PROVIDER", body.provider)
    if body.model:
        _write_env_key("LAST_MODEL", body.model)
    return {"ok": True}


@app.get("/api/settings/model")
async def get_model_settings():
    vals = dotenv_values(str(ENV_PATH))
    return {
        "last_provider": vals.get("LAST_PROVIDER", DEFAULT_PROVIDER),
        "last_model":    vals.get("LAST_MODEL", ""),
    }


# ── フォルダを開く（ローカル専用） ────────────────────────────
@app.post("/api/open_folder")
async def open_folder(body: dict):
    folder = body.get("folder", "pdf")
    if os.environ.get("RENDER") or os.environ.get("USE_DATA_DIR"):
        raise HTTPException(400, "クラウド環境ではフォルダを開けません")
    target = {"pdf": PDF_DIR, "csv": CSV_DIR, "archive": ARCHIVE_DIR}.get(folder)
    if target is None:
        raise HTTPException(422, "folder は pdf / csv / archive のいずれかです")
    import subprocess, sys
    if sys.platform == "win32":
        subprocess.Popen(["explorer", str(target)])
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(target)])
    else:
        subprocess.Popen(["xdg-open", str(target)])
    return {"ok": True, "path": str(target)}


# ── アーカイブ ────────────────────────────────────────────────
class ArchiveRequest(BaseModel):
    files: list[str]


@app.post("/api/archive")
async def archive_files(body: ArchiveRequest):
    moved = []
    for filename in body.files:
        src = (PDF_DIR / filename).resolve()
        try:
            src.relative_to(PDF_DIR.resolve())
        except ValueError:
            raise HTTPException(400, f"不正なパス: {filename}")
        if not src.exists():
            raise HTTPException(404, f"ファイルが見つかりません: {filename}")
        dest = ARCHIVE_DIR / src.name
        # 同名ファイルが既にある場合はサフィックスを付ける
        if dest.exists():
            dest = ARCHIVE_DIR / f"{src.stem}_{uuid.uuid4().hex[:6]}{src.suffix}"
        src.rename(dest)
        moved.append(src.name)
    return {"moved": moved}


# ── モデル一覧 ────────────────────────────────────────────────
@app.get("/api/models")
async def get_models():
    return {"providers": PROVIDERS, "default_provider": DEFAULT_PROVIDER}


# ── PDFファイル一覧 ────────────────────────────────────────────
@app.get("/api/pdf_files")
async def list_pdf_files():
    files = []
    for p in sorted(PDF_DIR.rglob("*")):
        if p.suffix.lower() != ".pdf":
            continue
        if any(part in SKIP_DIRS for part in p.relative_to(PDF_DIR).parts):
            continue
        files.append(str(p.relative_to(PDF_DIR)))
    return {"files": files}


# ── PDFアップロード ───────────────────────────────────────────
@app.post("/api/pdf_files/upload", status_code=201)
async def upload_pdf_files(files: list[UploadFile] = File(...)):
    saved = []
    for upload in files:
        name = Path(upload.filename).name
        if not name.lower().endswith(".pdf"):
            raise HTTPException(422, f"PDFファイルのみアップロード可能です: {name}")
        # パストラバーサル防止: ファイル名のみ使用
        dest = PDF_DIR / name
        content = await upload.read()
        dest.write_bytes(content)
        saved.append(name)
    return {"saved": saved}


# ── PDF削除 ───────────────────────────────────────────────────
class DeleteRequest(BaseModel):
    filename: str


@app.delete("/api/pdf_files")
async def delete_pdf_file(body: DeleteRequest):
    target = (PDF_DIR / body.filename).resolve()
    try:
        target.relative_to(PDF_DIR.resolve())
    except ValueError:
        raise HTTPException(400, "不正なパスです")
    if not target.exists():
        raise HTTPException(404, "ファイルが見つかりません")
    if not target.is_file():
        raise HTTPException(400, "ファイルではありません")
    target.unlink()
    return {"deleted": body.filename}


# ── ジョブ投入 ────────────────────────────────────────────────
class RunRequest(BaseModel):
    type: str          # "rename" | "process"
    files: list[str]   # PDF_DIR 相対パス。空 = 全件
    force: bool = False
    provider: str = DEFAULT_PROVIDER
    model: str = ""    # 空文字 = プロバイダーのデフォルト


@app.post("/api/run", status_code=202)
async def run_job(req: RunRequest):
    if req.type not in ("rename", "process"):
        raise HTTPException(422, "type は 'rename' または 'process' のみ有効です")

    if req.files:
        missing = [f for f in req.files if not (PDF_DIR / f).exists()]
        if missing:
            raise HTTPException(422, f"ファイルが見つかりません: {missing}")
        pdf_files = req.files
    else:
        pdf_files = []
        for p in sorted(PDF_DIR.rglob("*")):
            if p.suffix.lower() != ".pdf":
                continue
            if any(part in SKIP_DIRS for part in p.relative_to(PDF_DIR).parts):
                continue
            pdf_files.append(str(p.relative_to(PDF_DIR)))

    if not pdf_files:
        raise HTTPException(422, "処理対象のPDFファイルが見つかりません")

    job_id = uuid.uuid4().hex
    queue: asyncio.Queue = asyncio.Queue()
    jobs[job_id] = {
        "job_id":      job_id,
        "type":        req.type,
        "status":      "pending",
        "created_at":  _now(),
        "finished_at": None,
        "pdf_files":   pdf_files,
        "force":       req.force,
        "provider":    req.provider,
        "model":       req.model or None,
        "results":     [],
        "queue":       queue,
        "_done_payload": None,
        "_logs":       [],
    }

    _loop.run_in_executor(_executor, _run_job, job_id)
    return {"job_id": job_id}


# ── SSE ストリーム ────────────────────────────────────────────
@app.get("/api/jobs/{job_id}/stream")
async def stream_job(job_id: str):
    if job_id not in jobs:
        raise HTTPException(404, "ジョブが見つかりません")

    job = jobs[job_id]

    async def generate():
        # 既完了ジョブへの再接続: キャッシュ済みログを再送してから done を送る
        if job["_done_payload"] is not None:
            for log in job["_logs"]:
                yield f"data: {_json(log)}\n\n"
            yield f"event: done\ndata: {_json(job['_done_payload'])}\n\n"
            return

        # リアルタイムストリーム
        q: asyncio.Queue = job["queue"]
        while True:
            try:
                item = await asyncio.wait_for(q.get(), timeout=30)
            except asyncio.TimeoutError:
                yield ": keepalive\n\n"
                continue

            if item is None:
                # 終了センチネル → None を戻して次の接続に備える
                await q.put(None)
                break

            if isinstance(item, dict) and item.get("__event") == "done":
                yield f"event: done\ndata: {_json(item['data'])}\n\n"
                break

            yield f"data: {_json(item)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ── ジョブ結果（ポーリング用） ─────────────────────────────────
@app.get("/api/jobs/{job_id}/results")
async def job_results(job_id: str):
    if job_id not in jobs:
        raise HTTPException(404, "ジョブが見つかりません")
    job = jobs[job_id]
    if job["status"] in ("pending", "running"):
        return {"status": job["status"], "results": []}
    return {"status": job["status"], "results": job["results"]}


# ── 履歴 ──────────────────────────────────────────────────────
@app.get("/api/history")
async def history():
    result = []
    for job in sorted(jobs.values(), key=lambda j: j["created_at"], reverse=True):
        result.append({k: v for k, v in job.items() if k not in ("queue", "_done_payload", "_logs")})
    return {"jobs": result}


# ── ダウンロード ──────────────────────────────────────────────
@app.get("/api/download/{job_id}/{filename:path}")
async def download(job_id: str, filename: str):
    if job_id not in jobs:
        raise HTTPException(404, "ジョブが見つかりません")
    job = jobs[job_id]
    root = CSV_DIR if job["type"] == "process" else RENAMED_DIR
    resolved = (root / filename).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError:
        raise HTTPException(400, "不正なパスです")
    if not resolved.exists():
        raise HTTPException(404, "ファイルが見つかりません")
    from urllib.parse import quote
    encoded = quote(resolved.name, safe="")
    cd = f"attachment; filename*=UTF-8''{encoded}"
    return FileResponse(
        str(resolved),
        headers={"Content-Disposition": cd},
    )


# ── ジョブワーカー（スレッドプール内で実行） ───────────────────
def _run_job(job_id: str):
    job = jobs[job_id]
    job["status"] = "running"
    counter = [0]

    provider = job.get("provider", DEFAULT_PROVIDER)
    api_key = _get_api_key(provider)
    env_var = _env_var_for(provider)
    if not api_key:
        _put(job, counter, "error", f"{env_var} が設定されていません")
        _finish(job, "error")
        return

    model    = job.get("model") or None
    client = make_client(api_key, provider)

    def log_cb(level: str, text: str):
        _put(job, counter, level, text)

    results = []
    try:
        for rel in job["pdf_files"]:
            pdf_path = PDF_DIR / rel
            log_cb("info", f"処理開始: {rel}")
            if job["type"] == "rename":
                r = rename_one(pdf_path, client, RENAMED_DIR, log_cb, provider=provider, model=model)
            else:
                r = process_one(pdf_path, client, CSV_DIR, log_cb, force=job["force"],
                                provider=provider, model=model)
            results.append(dict(r))
    except FatalApiError as e:
        log_cb("error", f"致命的エラー: {e}")
        job["results"] = results
        _finish(job, "error")
        return

    job["results"] = results
    _finish(job, "done")


def _put(job: dict, counter: list, level: str, text: str):
    counter[0] += 1
    msg = {"level": level, "text": text, "id": counter[0]}
    job["_logs"].append(msg)
    asyncio.run_coroutine_threadsafe(job["queue"].put(msg), _loop).result()


def _finish(job: dict, status: str):
    job["status"] = status
    job["finished_at"] = _now()
    payload = {"results": job["results"], "status": status}
    job["_done_payload"] = payload
    asyncio.run_coroutine_threadsafe(
        job["queue"].put({"__event": "done", "data": payload}), _loop
    ).result()
    asyncio.run_coroutine_threadsafe(job["queue"].put(None), _loop).result()


# ── ユーティリティ ────────────────────────────────────────────
def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _mask(key: str) -> str:
    if len(key) <= 12:
        return "***"
    return key[:10] + "***" + key[-4:]


def _json(obj: Any) -> str:
    import json
    return json.dumps(obj, ensure_ascii=False)


def _write_env_key(env_var: str, key: str):
    lines = []
    replaced = False
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            if line.startswith(f"{env_var}="):
                lines.append(f"{env_var}={key}")
                replaced = True
            else:
                lines.append(line)
    if not replaced:
        lines.append(f"{env_var}={key}")
    tmp = ENV_PATH.with_suffix(".tmp")
    tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    tmp.replace(ENV_PATH)
