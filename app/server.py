"""Готовый учебный HTTP-сервис. Запускать одним процессом без reloader."""

import argparse
import json
import logging
import math
import os
from pathlib import Path
import re
import sys
import tempfile
import time
import uuid

from flask import Flask, g, jsonify, render_template, request
from werkzeug.exceptions import HTTPException

try:
    from . import settings
    from .analyzer import CSVError, analyze_bytes
except ImportError:
    import settings
    from analyzer import CSVError, analyze_bytes


def prepare_storage(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True, mode=0o755)
    reports = directory / "reports"
    try:
        reports.mkdir(mode=0o755)
    except FileExistsError:
        pass
    else:
        reports.chmod(0o755)
    # Проверяем фактическую запись от имени пользователя процесса, не только mode.
    for target in (directory, directory / "reports"):
        with tempfile.TemporaryFile(dir=target) as probe:
            probe.write(b"ready")
            probe.flush()
    journal = directory / "uploads.jsonl"
    try:
        with journal.open("x", encoding="utf-8") as stream:
            os.fchmod(stream.fileno(), 0o644)
    except FileExistsError:
        # После восстановления владелец может отличаться. Важен доступ,
        # а менять права чужих уже существующих файлов не требуется.
        with journal.open("a", encoding="utf-8"):
            pass


def create_app(data_dir=None, startup_delay=None) -> Flask:
    directory = Path(data_dir if data_dir is not None else settings.DATA_DIR).resolve()
    delay = settings.STARTUP_DELAY_SECONDS if startup_delay is None else startup_delay
    if not math.isfinite(delay) or not 0 <= delay <= 15:
        raise ValueError("STARTUP_DELAY_SECONDS должен быть числом от 0 до 15")
    prepare_storage(directory)
    ready_at = time.monotonic() + delay
    app = Flask(__name__, template_folder="templates")
    app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024
    app.json.ensure_ascii = False
    app.logger.setLevel(logging.INFO)

    @app.before_request
    def begin_request():
        g.request_id = uuid.uuid4().hex
        if request.path == "/health" or request.path.startswith("/reports"):
            if time.monotonic() < ready_at:
                return jsonify(status="starting", version=settings.VERSION, instance=settings.INSTANCE_NAME), 503

    @app.after_request
    def log_request(response):
        response.headers["X-Request-ID"] = g.request_id
        app.logger.info("request_id=%s method=%s path=%s status=%s", g.request_id, request.method, request.path, response.status_code)
        return response

    @app.errorhandler(HTTPException)
    def http_error(error):
        response = error.get_response()
        response.data = app.json.dumps({"error": error.description})
        response.content_type = "application/json"
        return response

    @app.errorhandler(OSError)
    def storage_error(error):
        app.logger.error("storage_error=%s", error)
        return jsonify(error="Ошибка доступа к хранилищу"), 503

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/health")
    def health():
        # Проверка готовности учитывает и доступность DATA_DIR после запуска.
        prepare_storage(directory)
        return jsonify(status="ok", version=settings.VERSION, instance=settings.INSTANCE_NAME)

    @app.get("/reports")
    def reports():
        return jsonify([json.loads(path.read_text(encoding="utf-8")) for path in sorted((directory / "reports").glob("*.json"))])

    @app.get("/reports/<report_id>")
    def report(report_id):
        if not re.fullmatch(r"[0-9a-f]{32}", report_id):
            return jsonify(error="Отчёт не найден"), 404
        path = directory / "reports" / f"{report_id}.json"
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return jsonify(error="Отчёт не найден"), 404
        return jsonify(value)

    @app.post("/reports")
    def submit():
        if request.mimetype != "multipart/form-data":
            return jsonify(error="Ожидается multipart/form-data с полем file"), 415
        upload = request.files.get("file")
        if upload is None or not upload.filename:
            return jsonify(error="Нужно передать CSV в поле file"), 422
        try:
            result = analyze_bytes(upload.read())
        except CSVError as exc:
            return jsonify(error=str(exc)), 422
        report_id = uuid.uuid4().hex
        filename = upload.filename.replace("\\", "/").rsplit("/", 1)[-1]
        result = {"id": report_id, "filename": filename, **result}
        target = directory / "reports" / f"{report_id}.json"
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=target.parent, prefix=".report-", delete=False) as stream:
                temporary = Path(stream.name)
                json.dump(result, stream, ensure_ascii=False, allow_nan=False)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            temporary.chmod(0o644)
            temporary.replace(target)
            with (directory / "uploads.jsonl").open("a", encoding="utf-8") as journal:
                journal.write(json.dumps({"id": report_id, "filename": filename, "request_id": g.request_id}, ensure_ascii=False) + "\n")
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        response = jsonify(result)
        response.status_code = 201
        response.headers["Location"] = f"/reports/{report_id}"
        return response

    return app


def main() -> int:
    parser = argparse.ArgumentParser(description="Учебный CSV API. Настройки через HOST, PORT, DATA_DIR, INSTANCE_NAME, STARTUP_DELAY_SECONDS (0..15). Подробности: interfaces.md.")
    parser.parse_args()
    try:
        app = create_app()
        if not 1 <= settings.PORT <= 65535:
            raise ValueError("PORT должен быть от 1 до 65535")
        app.run(host=settings.HOST, port=settings.PORT, debug=False, use_reloader=False, threaded=False)
    except (OSError, ValueError) as exc:
        print(f"Ошибка запуска: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
