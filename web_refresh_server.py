#!/usr/bin/env python3
import argparse
import json
import mimetypes
import subprocess
import threading
import uuid
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from core.action_store import acknowledge_entity, add_action_item, add_saved_view, add_watchlist_item, summarize_action_store, toggle_action_status, update_action_item
from core.auth import decode_jwt_payload, token_expiry_info
from core.http_client import create_session
from core.io_utils import write_json
from core.paths import JOB_RUNS_DIR, PROJECT_ROOT, ensure_dir
from core.quick_wins_state import load_state as qw_load_state, mark_done as qw_mark_done, mark_active as qw_mark_active, set_order as qw_set_order, _public as qw_public
from core.refresh_jobs import build_job_command, list_jobs, sanitize_payload
from core.reply_generator import generate_draft, load_config as load_reply_config
from core.reviews_api import post_question_answer, post_review_answer
from core.logging_config import get_logger
log = get_logger('web_refresh_server')


def now_iso():
    return datetime.now(timezone.utc).isoformat()


class JobStore:
    def __init__(self, base_dir):
        self.base_dir = ensure_dir(Path(base_dir))
        self.lock = threading.Lock()
        self.processes = {}

    def job_dir(self, job_id):
        return self.base_dir / job_id

    def status_path(self, job_id):
        return self.job_dir(job_id) / "status.json"

    def log_path(self, job_id):
        return self.job_dir(job_id) / "output.log"

    def write_status(self, job_id, payload):
        ensure_dir(self.job_dir(job_id))
        write_json(self.status_path(job_id), payload)

    def load_status(self, job_id):
        path = self.status_path(job_id)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def list_statuses(self):
        items = []
        for path in self.base_dir.glob("*/status.json"):
            try:
                items.append(json.loads(path.read_text(encoding="utf-8")))
            except Exception:
                continue
        items.sort(key=lambda row: row.get("started_at") or "", reverse=True)
        return items[:40]

    def append_log(self, job_id, line):
        ensure_dir(self.job_dir(job_id))
        with open(self.log_path(job_id), "a", encoding="utf-8") as handle:
            handle.write(line.rstrip("\n") + "\n")

    def _collect_artifacts_from_log(self, job_id):
        artifacts = []
        for raw_line in self.read_log(job_id).splitlines():
            line = raw_line.strip()
            if not line.startswith("Saved: "):
                continue
            path = line.replace("Saved: ", "", 1).strip()
            artifacts.append(
                {
                    "path": path,
                    "label": Path(path).name,
                    "download_url": f"/api/artifact?path={path}",
                }
            )
        deduped = []
        seen = set()
        for artifact in artifacts:
            key = artifact["path"]
            if key in seen:
                continue
            seen.add(key)
            deduped.append(artifact)
        return deduped

    def read_log(self, job_id):
        path = self.log_path(job_id)
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")[-50000:]

    def start_job(self, job_key, form_data):
        with self.lock:
            running = [proc for proc in self.processes.values() if proc.poll() is None]
            if running:
                raise RuntimeError("Another job is still running. Finish it before starting a new one.")
            job_id = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
            command = build_job_command(job_key, form_data)
            status = {
                "job_id": job_id,
                "job_key": job_key,
                "job_payload": sanitize_payload(job_key, form_data),
                "command": command,
                "state": "running",
                "started_at": now_iso(),
                "ended_at": None,
                "return_code": None,
                "line_count": 0,
                "progress_hint": "job started",
            }
            self.write_status(job_id, status)
            process = subprocess.Popen(
                command,
                cwd=str(PROJECT_ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                text=True,
                bufsize=1,
            )
            self.processes[job_id] = process
            threading.Thread(target=self._watch_job, args=(job_id, process), daemon=True).start()
            return status

    def _watch_job(self, job_id, process):
        line_count = 0
        try:
            for line in process.stdout or []:
                line_count += 1
                self.append_log(job_id, line)
                status = self.load_status(job_id) or {}
                status["line_count"] = line_count
                stripped = line.strip()
                if stripped:
                    status["progress_hint"] = stripped[:200]
                    status["artifacts"] = self._collect_artifacts_from_log(job_id)
                self.write_status(job_id, status)
            return_code = process.wait()
            status = self.load_status(job_id) or {}
            status["state"] = "succeeded" if return_code == 0 else "failed"
            status["return_code"] = return_code
            status["ended_at"] = now_iso()
            status["line_count"] = line_count
            status["artifacts"] = self._collect_artifacts_from_log(job_id)
            if status["state"] == "succeeded" and status.get("progress_hint") == "job started":
                status["progress_hint"] = "job finished"
            self.write_status(job_id, status)
        finally:
            with self.lock:
                self.processes.pop(job_id, None)


class RefreshHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, directory=None, job_store=None, **kwargs):
        self.job_store = job_store
        super().__init__(*args, directory=directory, **kwargs)

    def _send_json(self, payload, status=HTTPStatus.OK):
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Cache-Control", "no-store, max-age=0")
        super().end_headers()

    def _read_json_body(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw.decode("utf-8"))

    def do_OPTIONS(self):
        self.send_response(HTTPStatus.NO_CONTENT)
        self.end_headers()

    def _rewrite_static_path(self):
        parsed = urlparse(self.path)
        if parsed.path in {"/", "/index.html"}:
            self.path = "/docs/index.html"
            return True
        if parsed.path == "/refresh.html":
            self.path = "/docs/index.html"
            return True
        if parsed.path in {
            "/styles.css",
            "/app.js",
            "/api.js",
            "/components.js",
            "/dashboard_views.js",
            "/refresh.js",
            "/state.js",
        }:
            self.path = f"/docs{parsed.path}"
            return True
        return False

    def _send_file(self, path):
        file_path = Path(path).resolve()
        project_root = PROJECT_ROOT.resolve()
        if project_root not in file_path.parents and file_path != project_root:
            self._send_json({"error": "path outside project root"}, status=HTTPStatus.FORBIDDEN)
            return
        if not file_path.exists() or not file_path.is_file():
            self._send_json({"error": "artifact not found"}, status=HTTPStatus.NOT_FOUND)
            return
        body = file_path.read_bytes()
        content_type, _ = mimetypes.guess_type(str(file_path))
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type or "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Content-Disposition", f'inline; filename="{file_path.name}"')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        if self._rewrite_static_path():
            return super().do_GET()
        if parsed.path == "/api/jobs":
            self._send_json({"jobs": list_jobs()})
            return
        if parsed.path == "/api/runs":
            self._send_json({"runs": self.job_store.list_statuses()})
            return
        if parsed.path == "/api/action-center":
            self._send_json(summarize_action_store())
            return
        if parsed.path == "/api/reviews":
            reviews_file = PROJECT_ROOT / "data" / "reviews" / "reviews.json"
            if not reviews_file.exists():
                self._send_json({"items": [], "fetched_at": None, "count": 0, "status": "no_data"})
            else:
                import json as _json
                payload = _json.loads(reviews_file.read_text(encoding="utf-8"))
                self._send_json(payload)
            return
        if parsed.path == "/api/quick_wins/state":
            import datetime as _dt
            session_date = parse_qs(parsed.query).get("date", [_dt.date.today().isoformat()])[0]
            state = qw_load_state(session_date)
            self._send_json({"ok": True, "state": qw_public(state)})
            return
        if parsed.path == "/api/artifact":
            target = parse_qs(parsed.query).get("path", [None])[0]
            if not target:
                self._send_json({"error": "missing path"}, status=HTTPStatus.BAD_REQUEST)
                return
            self._send_file(target)
            return
        if parsed.path == "/api/run":
            job_id = parse_qs(parsed.query).get("job_id", [None])[0]
            status = self.job_store.load_status(job_id) if job_id else None
            if not status:
                self._send_json({"error": "job not found"}, status=HTTPStatus.NOT_FOUND)
                return
            self._send_json({"status": status, "log": self.job_store.read_log(job_id)})
            return
        return super().do_GET()

    def do_HEAD(self):
        self._rewrite_static_path()
        return super().do_HEAD()

    def do_POST(self):
        parsed = urlparse(self.path)
        try:
            payload = self._read_json_body()
            if parsed.path == "/api/run":
                status = self.job_store.start_job(payload["job_key"], payload.get("form_data") or {})
                self._send_json({"status": status}, status=HTTPStatus.CREATED)
                return
            if parsed.path == "/api/action-center/watchlist":
                item = add_watchlist_item(payload)
                self._send_json({"item": item, "store": summarize_action_store()}, status=HTTPStatus.CREATED)
                return
            if parsed.path == "/api/action-center/action":
                item = add_action_item(payload)
                self._send_json({"item": item, "store": summarize_action_store()}, status=HTTPStatus.CREATED)
                return
            if parsed.path == "/api/action-center/action/update":
                item = update_action_item(payload)
                self._send_json({"item": item, "store": summarize_action_store()}, status=HTTPStatus.OK)
                return
            if parsed.path == "/api/action-center/acknowledge":
                item = acknowledge_entity(payload)
                self._send_json({"item": item, "store": summarize_action_store()}, status=HTTPStatus.CREATED)
                return
            if parsed.path == "/api/action-center/toggle":
                item = toggle_action_status(payload["id"])
                self._send_json({"item": item, "store": summarize_action_store()}, status=HTTPStatus.OK)
                return
            if parsed.path == "/api/action-center/view":
                item = add_saved_view(payload)
                self._send_json({"item": item, "store": summarize_action_store()}, status=HTTPStatus.CREATED)
                return
            if parsed.path == "/api/reviews/generate":
                item = payload.get("item")
                llm_api_key = (payload.get("llm_api_key") or "").strip() or None
                if not item:
                    self._send_json({"error": "missing item"}, status=HTTPStatus.BAD_REQUEST)
                    return
                config = load_reply_config()
                draft = generate_draft(item, config, llm_api_key=llm_api_key)
                self._send_json({"draft": draft})
                return
            if parsed.path == "/api/reviews/send":
                token = (payload.get("token") or "").strip()
                item = payload.get("item")
                text = (payload.get("text") or "").strip()
                if not token or not item or not text:
                    self._send_json({"error": "missing token, item or text"}, status=HTTPStatus.BAD_REQUEST)
                    return
                session = create_session()
                item_id = item.get("id")
                kind = item.get("kind", "review")
                try:
                    if kind == "question":
                        result = post_question_answer(session, token, item_id, text)
                    else:
                        result = post_review_answer(session, token, item_id, text)
                    self._send_json({"ok": True, "result": result})
                except Exception as exc:
                    self._send_json({"error": str(exc)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
                return
            if parsed.path == "/api/quick_wins/complete":
                import datetime as _dt
                session_date = payload.get("date") or _dt.date.today().isoformat()
                item_id = payload["id"]
                state = qw_mark_done(session_date, item_id)
                self._send_json({"ok": True, "state": qw_public(state)})
                return
            if parsed.path == "/api/quick_wins/restore":
                import datetime as _dt
                session_date = payload.get("date") or _dt.date.today().isoformat()
                item_id = payload["id"]
                state = qw_mark_active(session_date, item_id)
                self._send_json({"ok": True, "state": qw_public(state)})
                return
            if parsed.path == "/api/quick_wins/reorder":
                import datetime as _dt
                session_date = payload.get("date") or _dt.date.today().isoformat()
                order = payload.get("order", [])
                state = qw_set_order(session_date, order)
                self._send_json({"ok": True, "state": qw_public(state)})
                return
            if parsed.path == "/api/token-health":
                token = (payload.get("token") or "").strip()
                if not token:
                    self._send_json({"error": "missing token"}, status=HTTPStatus.BAD_REQUEST)
                    return
                decoded = decode_jwt_payload(token)
                info = token_expiry_info(token)
                if not decoded:
                    self._send_json(
                        {
                            "ok": False,
                            "token_health": info,
                            "error": "token format is invalid or payload cannot be decoded",
                        },
                        status=HTTPStatus.BAD_REQUEST,
                    )
                    return
                self._send_json(
                    {
                        "ok": info.get("status") == "valid",
                        "token_health": info,
                        "payload": {
                            "uid": decoded.get("uid"),
                            "sub": decoded.get("sub"),
                            "exp": decoded.get("exp"),
                        },
                    }
                )
                return
            if parsed.path == "/api/ingest":
                import base64 as _b64
                import tempfile as _tmp
                import sys as _sys2
                filename = str(payload.get("filename", "upload")).strip()
                data_b64 = str(payload.get("data_b64", "")).strip()
                token = str(payload.get("token", "")).strip()
                if not data_b64:
                    self._send_json({"error": "missing data_b64"}, status=HTTPStatus.BAD_REQUEST)
                    return
                try:
                    file_bytes = _b64.b64decode(data_b64)
                except Exception as exc:
                    self._send_json({"error": f"invalid base64: {exc}"}, status=HTTPStatus.BAD_REQUEST)
                    return
                suffix = Path(filename).suffix.lower() or ".bin"
                with _tmp.NamedTemporaryFile(suffix=suffix, delete=False) as tf:
                    tf.write(file_bytes)
                    tmp_path = Path(tf.name)
                result_path = PROJECT_ROOT / "data" / "ingest_result.json"
                cmd = [
                    _sys2.executable, "scripts/ingest.py",
                    "--file", str(tmp_path),
                    "--output-json", str(result_path),
                ]
                if token:
                    cmd += ["--token", token]
                try:
                    proc = subprocess.run(
                        cmd,
                        cwd=str(PROJECT_ROOT),
                        capture_output=True,
                        text=True,
                        timeout=120,
                    )
                    try:
                        result_data = json.loads(result_path.read_text(encoding="utf-8")) if result_path.exists() else {}
                    except Exception:
                        result_data = {}
                    if not result_data:
                        result_data = {"ok": proc.returncode == 0, "log": [(proc.stdout + proc.stderr).strip()]}
                    self._send_json(result_data)
                except subprocess.TimeoutExpired:
                    self._send_json({"error": "ingest timed out (120s)"}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
                except Exception as exc:
                    self._send_json({"error": str(exc)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
                finally:
                    try:
                        tmp_path.unlink(missing_ok=True)
                    except Exception:
                        pass
                return
            if parsed.path == "/api/ab_compare":
                import datetime as _dt
                import re as _re
                import sys as _sys
                product_id = str(payload.get("product_id", "")).strip()
                applied_date = str(payload.get("applied_date", "")).strip()
                token = (payload.get("token") or "").strip()
                if not product_id or not applied_date or not token:
                    self._send_json({"error": "missing product_id, applied_date or token"}, status=HTTPStatus.BAD_REQUEST)
                    return
                if not _re.match(r'^\d{4}-\d{2}-\d{2}$', applied_date):
                    self._send_json({"error": "invalid applied_date, expected YYYY-MM-DD"}, status=HTTPStatus.BAD_REQUEST)
                    return
                a_start = applied_date
                a_end = _dt.date.today().isoformat()
                b_end = applied_date
                b_start = (_dt.date.fromisoformat(applied_date) - _dt.timedelta(days=7)).isoformat()
                prefix = f"ab_result_{product_id}_{applied_date}"
                from core.paths import REPORTS_DIR
                cmd = [
                    _sys.executable, "scripts/ab_compare.py",
                    "--token", token,
                    "--a-product-id", product_id,
                    "--a-date-range", f'["{a_start}","{a_end}"]',
                    "--b-product-id", product_id,
                    "--b-date-range", f'["{b_start}","{b_end}"]',
                    "--report-prefix", prefix,
                ]
                try:
                    proc = subprocess.run(
                        cmd,
                        cwd=str(PROJECT_ROOT),
                        capture_output=True,
                        text=True,
                        timeout=90,
                    )
                    if proc.returncode != 0:
                        self._send_json(
                            {"error": (proc.stdout + proc.stderr).strip() or "ab_compare failed"},
                            status=HTTPStatus.INTERNAL_SERVER_ERROR,
                        )
                        return
                    result_path = REPORTS_DIR / f"{prefix}.json"
                    if not result_path.exists():
                        self._send_json({"error": "result file not found after run"}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
                        return
                    data = json.loads(result_path.read_text(encoding="utf-8"))
                    self._send_json({"ok": True, "result": data, "log": proc.stdout})
                except subprocess.TimeoutExpired:
                    self._send_json({"error": "ab_compare timed out (90s)"}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
                except Exception as exc:
                    self._send_json({"error": str(exc)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
                return
            self._send_json({"error": "unknown path"}, status=HTTPStatus.NOT_FOUND)
        except Exception as exc:
            self._send_json({"error": str(exc)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)


def main():
    parser = argparse.ArgumentParser(description="MM Market Tools — Local dashboard server")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", default="localhost")
    args = parser.parse_args()

    job_store = JobStore(JOB_RUNS_DIR)
    handler = lambda *a, **kw: RefreshHandler(*a, directory=str(PROJECT_ROOT), job_store=job_store, **kw)
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(f"Serving at http://{args.host}:{args.port} — Press Ctrl+C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
