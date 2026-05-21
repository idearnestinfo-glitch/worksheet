#!/usr/bin/env python3
# IDEARNEST WORKSHEET ローカルサーバ
# 編集機能を使うときに起動。停止は Ctrl+C
#
# 使い方:
#   cd ~/IDEARNEST && python3 scripts/serve.py
#   ブラウザで http://localhost:8765/ui/index.html を開く

import http.server
import json
import os
import re
import socketserver
import subprocess
import sys
import threading
import unicodedata
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PORT = 8765

# 議事録モジュールを ~/meeting/lib から読み込む
MEETING_LIB = Path.home() / "meeting" / "lib"
if MEETING_LIB.exists() and str(MEETING_LIB) not in sys.path:
    sys.path.insert(0, str(MEETING_LIB))


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, format, *args):
        # 静かにする
        if "POST" in (args[0] if args else ""):
            super().log_message(format, *args)

    def do_POST(self):
        if self.path == "/api/save":
            return self._save()
        if self.path == "/api/regenerate":
            return self._regen()
        if self.path == "/api/update-status":
            return self._update_status()
        if self.path == "/api/minutes/create":
            return self._minutes_create()
        if self.path == "/api/minutes/save":
            return self._minutes_save()
        if self.path == "/api/minutes/delete":
            return self._minutes_delete()
        if self.path == "/api/minutes/upload-audio":
            return self._minutes_upload_audio()
        if self.path == "/api/minutes/from-audio":
            return self._minutes_from_audio()
        if self.path == "/api/minutes/preview-apply":
            return self._minutes_preview_apply()
        if self.path == "/api/minutes/apply":
            return self._minutes_apply()
        self.send_error(404, "Unknown endpoint")

    def do_GET(self):
        if self.path.startswith("/api/minutes/get"):
            return self._minutes_get()
        return super().do_GET()

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length).decode("utf-8")) if length else {}

    def _send_json(self, status, payload):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))

    def _save(self):
        try:
            data = self._read_body()
            target = self._find_job_file(data)
            if target is None:
                # 新規（既存ファイルが見つからない）
                target = self._build_new_job_filename(data)
            data["更新日"] = datetime.now().strftime("%Y-%m-%d")
            target.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            self._regenerate_data_js()
            self._send_json(200, {"ok": True, "file": str(target.relative_to(ROOT))})
        except Exception as e:
            self._send_json(500, {"ok": False, "error": str(e)})

    def _regen(self):
        try:
            self._regenerate_data_js()
            self._send_json(200, {"ok": True})
        except Exception as e:
            self._send_json(500, {"ok": False, "error": str(e)})

    def _update_status(self):
        """状態フィールドだけ更新して data.js を再ビルド"""
        try:
            body = self._read_body()
            new_status = body.get("状態")
            if not new_status:
                self._send_json(400, {"ok": False, "error": "状態 is required"})
                return
            target = self._find_job_file(body)
            if target is None:
                self._send_json(404, {"ok": False, "error": "Job not found"})
                return
            existing = json.loads(target.read_text(encoding="utf-8"))
            existing["状態"] = new_status
            existing["更新日"] = datetime.now().strftime("%Y-%m-%d")
            target.write_text(json.dumps(existing, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            self._regenerate_data_js()
            self._send_json(200, {"ok": True, "file": str(target.relative_to(ROOT))})
        except Exception as e:
            self._send_json(500, {"ok": False, "error": str(e)})

    def _find_job_file(self, data):
        jobs_dir = ROOT / "data" / "jobs"
        target_id = data.get("制作番号")
        target_tt = data.get("TickTick_task_id")
        for p in jobs_dir.glob("*.json"):
            try:
                existing = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                continue
            if target_id is not None and existing.get("制作番号") == target_id:
                return p
            if target_tt and existing.get("TickTick_task_id") == target_tt:
                return p
        return None

    def _build_new_job_filename(self, data):
        # 撮影 / 通常 で命名分岐
        seg_id = str(data.get("制作番号") or "撮影")
        client = self._safe_filename(data.get("クライアント") or "")
        product = self._safe_filename(data.get("製品名") or "")
        product = product[:40]
        name = f"{seg_id}_{client}_{product}.json".replace("/", "_")
        return ROOT / "data" / "jobs" / name

    @staticmethod
    def _safe_filename(s):
        s = unicodedata.normalize("NFKC", s)
        return re.sub(r"[\\/:*?\"<>|]+", "_", s).strip()

    def _regenerate_data_js(self):
        subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "build_data_js.py")],
            check=True,
            cwd=ROOT,
            capture_output=True,
        )

    # ====== 議事録 API ======

    def _minutes_create(self):
        """テキスト + メタ情報を受けて Claude API で構造化、保存して返す。"""
        try:
            body = self._read_body()
            text = body.get("text", "")
            if not text.strip():
                return self._send_json(400, {"ok": False, "error": "text is required"})

            from digest import digest_text
            from store import build_record, save_minute

            today = body.get("today") or datetime.now().strftime("%Y-%m-%d")
            digest = digest_text(
                text=text,
                source_type=body.get("source_type", "manual"),
                today=today,
                client_hint=body.get("client_hint"),
                job_hint=body.get("job_hint"),
            )
            record = build_record(
                digest=digest,
                source_type=body.get("source_type", "manual"),
                raw_input=text,
                date=body.get("date") or today,
                time=body.get("time") or datetime.now().strftime("%H:%M"),
                source_meta=body.get("source_meta") or {},
            )
            # ヒント情報の補完
            if body.get("client_hint") and not record.get("client_id"):
                record["client_id"] = body["client_hint"]
            if body.get("job_hint") and not record.get("job_no"):
                record["job_no"] = str(body["job_hint"])

            save_minute(record)
            self._regenerate_data_js()
            return self._send_json(200, {"ok": True, "minute": record})
        except Exception as e:
            return self._send_json(500, {"ok": False, "error": str(e)})

    def _minutes_save(self):
        """編集済みの議事録レコードをそのまま保存（フォーム編集用）。"""
        try:
            body = self._read_body()
            from store import save_minute
            if not body.get("id"):
                return self._send_json(400, {"ok": False, "error": "id is required"})
            save_minute(body)
            self._regenerate_data_js()
            return self._send_json(200, {"ok": True})
        except Exception as e:
            return self._send_json(500, {"ok": False, "error": str(e)})

    def _minutes_get(self):
        """単体取得。transcript / raw_input を含むフルデータを返す。"""
        try:
            from urllib.parse import urlparse, parse_qs
            from store import load_minute
            qs = parse_qs(urlparse(self.path).query)
            mid = (qs.get("id") or [""])[0]
            if not mid:
                return self._send_json(400, {"ok": False, "error": "id is required"})
            rec = load_minute(mid)
            if not rec:
                return self._send_json(404, {"ok": False, "error": "not found"})
            return self._send_json(200, {"ok": True, "minute": rec})
        except Exception as e:
            return self._send_json(500, {"ok": False, "error": str(e)})

    def _minutes_delete(self):
        try:
            body = self._read_body()
            from store import find_by_id
            mid = body.get("id")
            if not mid:
                return self._send_json(400, {"ok": False, "error": "id is required"})
            p = find_by_id(mid)
            if not p:
                return self._send_json(404, {"ok": False, "error": "not found"})
            p.unlink()
            self._regenerate_data_js()
            return self._send_json(200, {"ok": True})
        except Exception as e:
            return self._send_json(500, {"ok": False, "error": str(e)})

    # ====== 音声議事録 API ======

    def _parse_multipart(self, content_type: str, body: bytes) -> dict:
        """マルチパート/フォームデータの簡易パーサ。単一ファイル + フォーム値想定。"""
        m = re.search(r"boundary=([^;]+)", content_type)
        if not m:
            raise ValueError("multipart境界が不明")
        boundary = m.group(1).strip().strip('"')
        boundary_bytes = ("--" + boundary).encode()
        parts = body.split(boundary_bytes)
        # 先頭・末尾は preamble / epilogue
        result = {}
        for raw in parts:
            if raw.startswith(b"\r\n"):
                raw = raw[2:]
            if raw.endswith(b"\r\n"):
                raw = raw[:-2]
            if not raw or raw == b"--" or raw.startswith(b"--"):
                continue
            header_end = raw.find(b"\r\n\r\n")
            if header_end == -1:
                continue
            headers = raw[:header_end].decode("utf-8", errors="ignore")
            content = raw[header_end + 4:]
            name_match = re.search(r'name="([^"]+)"', headers)
            if not name_match:
                continue
            name = name_match.group(1)
            filename_match = re.search(r'filename="([^"]+)"', headers)
            if filename_match:
                result[name] = {"filename": filename_match.group(1), "content": content}
            else:
                result[name] = content.decode("utf-8", errors="ignore")
        return result

    def _start_audio_processing(self, audio_path: str, meta: dict) -> dict:
        """音声処理スレッドを起動し、stub議事録レコードを保存・返す。"""
        from store import build_record, save_minute, make_id

        today = meta.get("date") or datetime.now().strftime("%Y-%m-%d")
        time = meta.get("time") or datetime.now().strftime("%H:%M")
        client_hint = meta.get("client_hint")
        job_hint = meta.get("job_hint")

        digest_stub = {
            "title": f"音声議事録 (処理中) - {Path(audio_path).name}",
            "client_id": client_hint,
            "job_no": str(job_hint) if job_hint else None,
            "summary": "(文字起こし中...)",
            "decisions": [], "new_requests": [], "modifications": [],
            "schedules": [], "next_actions": [], "tags": [],
        }
        record = build_record(
            digest=digest_stub,
            source_type="audio",
            raw_input=audio_path,
            date=today,
            time=time,
            source_meta={
                "audio_filename": Path(audio_path).name,
                "audio_path": audio_path,
            },
        )
        record["status"] = "processing_transcribe"
        record["status_message"] = "文字起こし開始..."
        save_minute(record)
        self._regenerate_data_js()

        # バックグラウンド処理
        t = threading.Thread(
            target=_audio_pipeline_worker,
            args=(record["id"], audio_path, client_hint, job_hint, today, time),
            daemon=True,
        )
        t.start()

        return record

    def _minutes_upload_audio(self):
        """multipart/form-data で音声ファイルアップロード。バックグラウンドで処理開始。"""
        try:
            content_type = self.headers.get("Content-Type", "")
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            parts = self._parse_multipart(content_type, body)

            file_part = parts.get("audio")
            if not file_part or not isinstance(file_part, dict):
                return self._send_json(400, {"ok": False, "error": "audio file is required"})

            filename = file_part["filename"]
            content = file_part["content"]

            # 保存先
            audio_dir = ROOT / "data" / "minutes" / "audio"
            audio_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_name = re.sub(r"[\\/:*?\"<>|]+", "_", filename)
            saved_path = audio_dir / f"{ts}_{safe_name}"
            saved_path.write_bytes(content)

            meta = {
                "client_hint": parts.get("client_hint") or None,
                "job_hint": parts.get("job_hint") or None,
                "date": parts.get("date") or None,
                "time": parts.get("time") or None,
            }

            record = self._start_audio_processing(str(saved_path), meta)
            return self._send_json(200, {"ok": True, "minute_id": record["id"], "minute": record})
        except Exception as e:
            return self._send_json(500, {"ok": False, "error": str(e)})

    def _minutes_from_audio(self):
        """JSON でファイルパスを指定（CLI/Claude Codeセッション経由）。"""
        try:
            body = self._read_body()
            audio_path = body.get("audio_path")
            if not audio_path:
                return self._send_json(400, {"ok": False, "error": "audio_path is required"})
            audio_path = str(Path(audio_path).expanduser().resolve())
            if not Path(audio_path).exists():
                return self._send_json(404, {"ok": False, "error": f"audio file not found: {audio_path}"})

            record = self._start_audio_processing(audio_path, {
                "client_hint": body.get("client_hint"),
                "job_hint": body.get("job_hint"),
                "date": body.get("date"),
                "time": body.get("time"),
            })
            return self._send_json(200, {"ok": True, "minute_id": record["id"], "minute": record})
        except Exception as e:
            return self._send_json(500, {"ok": False, "error": str(e)})

    def _minutes_preview_apply(self):
        """議事録から「何を作る/更新するか」のプランを返す（実行はしない）。"""
        try:
            body = self._read_body()
            from store import load_minute
            from apply import build_preview
            mid = body.get("id")
            if not mid:
                return self._send_json(400, {"ok": False, "error": "id is required"})
            rec = load_minute(mid)
            if not rec:
                return self._send_json(404, {"ok": False, "error": "not found"})
            preview = build_preview(rec)
            return self._send_json(200, {"ok": True, "minute": rec, **preview})
        except Exception as e:
            return self._send_json(500, {"ok": False, "error": str(e)})

    def _minutes_apply(self):
        """選択されたプランを実行して TickTick / WORKSHEET に反映。"""
        try:
            body = self._read_body()
            from store import load_minute, save_minute
            from apply import apply_selected
            mid = body.get("id")
            if not mid:
                return self._send_json(400, {"ok": False, "error": "id is required"})
            rec = load_minute(mid)
            if not rec:
                return self._send_json(404, {"ok": False, "error": "not found"})

            indices = body.get("selected_indices", [])
            result = apply_selected(rec, indices)

            # applied メタを更新
            rec.setdefault("applied", {})
            rec["applied"]["applied_at"] = datetime.now().isoformat(timespec="seconds")
            rec["applied"]["applied_by"] = "user"
            rec["applied"]["selected_indices"] = indices
            rec["applied"]["succeeded_count"] = result["succeeded_count"]
            rec["applied"]["failed_count"] = result["failed_count"]
            # ticktick_task_ids / worksheet_updates を集計
            tt_ids = []
            for r in result["results"]:
                if r.get("ok") and r.get("task_id"):
                    tt_ids.append(r["task_id"])
            rec["applied"]["ticktick_task_ids"] = tt_ids
            save_minute(rec)
            self._regenerate_data_js()
            return self._send_json(200, {"ok": True, "minute": rec, **result})
        except Exception as e:
            return self._send_json(500, {"ok": False, "error": str(e)})


def _audio_pipeline_worker(minute_id, audio_path, client_hint, job_hint, date, time):
    """音声 → 文字起こし → 議事録化のバックグラウンドパイプライン。

    - 各ステップで議事録JSONを更新（status / status_message）
    - 失敗時は status="error" と error_message を残す
    """
    from store import load_minute, save_minute, build_record
    from transcribe import transcribe, TranscribeError
    from digest import digest_text

    def _update_status(status, msg, **extra):
        rec = load_minute(minute_id)
        if not rec:
            return
        rec["status"] = status
        rec["status_message"] = msg
        for k, v in extra.items():
            rec[k] = v
        save_minute(rec)
        try:
            subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "build_data_js.py")],
                check=False, cwd=ROOT, capture_output=True,
            )
        except Exception:
            pass

    try:
        # 1. 文字起こし
        _update_status("processing_transcribe", "文字起こし中...")
        # クライアント名を initial_prompt として渡すと固有名詞精度が上がる
        prompt = client_hint if client_hint else None
        result = transcribe(
            audio_path=audio_path,
            language="ja",
            initial_prompt=prompt,
        )
        transcript = result["transcript"]
        duration_sec = result.get("duration_sec")

        # 2. 議事録化
        _update_status(
            "processing_digest",
            f"議事録化中... ({len(transcript)}文字)",
            transcript=transcript,
            source_meta={
                "audio_filename": Path(audio_path).name,
                "audio_path": audio_path,
                "duration_sec": duration_sec,
                "transcribe_model": result.get("model"),
            },
        )

        digest = digest_text(
            text=transcript,
            source_type="audio",
            today=date,
            client_hint=client_hint,
            job_hint=job_hint,
        )

        # 3. レコード再構築
        rec = load_minute(minute_id)
        rec["title"] = digest.get("title", rec.get("title", ""))
        if digest.get("client_id") and not client_hint:
            rec["client_id"] = digest["client_id"]
        if digest.get("job_no") and not job_hint:
            rec["job_no"] = str(digest["job_no"])
        rec["summary"] = digest.get("summary", "")
        rec["decisions"] = digest.get("decisions", [])
        rec["new_requests"] = digest.get("new_requests", [])
        rec["modifications"] = digest.get("modifications", [])
        rec["schedules"] = digest.get("schedules", [])
        rec["next_actions"] = digest.get("next_actions", [])
        rec["tags"] = digest.get("tags", [])
        rec["status"] = "ready"
        rec["status_message"] = "完了"
        save_minute(rec)
        subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "build_data_js.py")],
            check=False, cwd=ROOT, capture_output=True,
        )
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        _update_status("error", f"処理失敗: {str(e)[:300]}", error_traceback=tb[:2000])


class ThreadingHTTPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    daemon_threads = True
    allow_reuse_address = True


def main():
    os.chdir(ROOT)
    # 起動時に最新化
    subprocess.run([sys.executable, str(ROOT / "scripts" / "build_data_js.py")], check=False, cwd=ROOT)
    with ThreadingHTTPServer(("0.0.0.0", PORT), Handler) as httpd:
        import socket
        hostname = socket.gethostname()
        # Tailscale IP を取得（あれば表示）
        try:
            ts_ip = subprocess.check_output(
                ["tailscale", "ip", "-4"], text=True, stderr=subprocess.DEVNULL
            ).strip()
        except Exception:
            ts_ip = None
        print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print(f"IDEARNEST WORKSHEET サーバ起動")
        print(f"  ローカル: http://localhost:{PORT}/ui/index.html")
        if ts_ip:
            print(f"  Tailscale: http://{ts_ip}:{PORT}/ui/index.html")
        else:
            print(f"  Tailscale: （tailscale 未接続）")
        print(f"  停止: Ctrl+C")
        print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n停止しました")


if __name__ == "__main__":
    main()
