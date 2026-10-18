"""Strict local model calls with reproducible request/response evidence."""
import json
import os
import urllib.request
from datetime import datetime
from pathlib import Path
from uuid import uuid4

BASE_DIR = Path(__file__).resolve().parent
MODEL_NAME = "qwen3:8b"


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def chat(stage, system_prompt, user_prompt, response_format=None):
    evidence_dir = Path(os.environ.get("SCSE_EVIDENCE_DIR", BASE_DIR / "artifacts" / "model_calls"))
    path = evidence_dir / f"{datetime.now():%Y%m%dT%H%M%S}-{stage}-{uuid4().hex[:8]}.json"
    data = {
        "model": MODEL_NAME,
        "messages": [{"role": "system", "content": system_prompt},
                     {"role": "user", "content": user_prompt}],
        "stream": False, "think": False, "keep_alive": 0,
        "options": {"temperature": 0, "seed": 42, "num_ctx": 8192,
                    "num_predict": 2400, "num_gpu": 0, "num_thread": 4},
    }
    if response_format is not None:
        data["format"] = response_format
    record = {"stage": stage, "source": "ollama_live", "status": "started", "request": data}
    write_json(path, record)
    try:
        request = urllib.request.Request(
            "http://127.0.0.1:11434/api/chat", data=json.dumps(data).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(request, timeout=900) as response:
            result = json.load(response)
        record["response"] = result
        if not result.get("done") or result.get("done_reason") == "length":
            raise ValueError("Model output was incomplete or truncated.")
        content = result["message"]["content"]
        if not isinstance(content, str) or not content.strip():
            raise ValueError("Model returned empty content.")
        record["status"] = "received"
        return content
    except Exception as exc:
        record.update(status="error", error=f"{type(exc).__name__}: {exc}")
        raise RuntimeError(f"{stage}: live Qwen call failed; no fallback used. Evidence: {path}") from exc
    finally:
        record["finished_at"] = datetime.now().isoformat()
        write_json(path, record)
