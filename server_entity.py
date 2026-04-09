#!/usr/bin/env python3
"""
结算工作台 Entity 版 - 局域网协作服务
用法:
    pip install flask flask-cors
    python3 server_entity.py
访问: http://<你的局域网IP>:8766
"""

import json
import os
import queue
import threading
import time
from pathlib import Path

from flask import Flask, Response, jsonify, request, send_from_directory
from flask_cors import CORS

app = Flask(__name__, static_folder=".")
CORS(app)

# ── 数据持久化路径 ────────────────────────────────────────────
STATE_FILE = Path(__file__).parent / "workbench_entity_state.json"

# ── SSE 广播 ─────────────────────────────────────────────────
_subscribers: list[queue.Queue] = []
_subscribers_lock = threading.Lock()


def _broadcast(event_type: str, data: str = "{}"):
    """向所有已连接的 SSE 客户端推送事件。"""
    msg = f"event: {event_type}\ndata: {data}\n\n"
    with _subscribers_lock:
        dead = []
        for q in _subscribers:
            try:
                q.put_nowait(msg)
            except queue.Full:
                dead.append(q)
        for q in dead:
            _subscribers.remove(q)


def _sse_stream(q: queue.Queue):
    """生成器：持续从队列取消息发给客户端，客户端断开时退出。"""
    try:
        yield ": ping\n\n"
        while True:
            try:
                msg = q.get(timeout=25)
                yield msg
            except queue.Empty:
                yield ": ping\n\n"
    except GeneratorExit:
        pass
    finally:
        with _subscribers_lock:
            if q in _subscribers:
                _subscribers.remove(q)


# ── 状态读写 ─────────────────────────────────────────────────
def _load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"periods": {}, "currentPeriod": None}


def _save_state(data: dict):
    STATE_FILE.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


# ── 路由 ─────────────────────────────────────────────────────

@app.route("/")
def index():
    """把 Entity 版 HTML 工作台作为首页提供。"""
    return send_from_directory(".", "结算工作台-entity版.html")


@app.route("/api/state", methods=["GET"])
def get_state():
    return jsonify(_load_state())


@app.route("/api/state", methods=["POST"])
def post_state():
    data = request.get_json(force=True, silent=True)
    if data is None:
        return jsonify({"error": "invalid json"}), 400
    _save_state(data)
    _broadcast("state_updated")
    return jsonify({"ok": True})


@app.route("/api/events")
def sse_events():
    """SSE 端点：客户端订阅后实时收到 state_updated 事件。"""
    q: queue.Queue = queue.Queue(maxsize=20)
    with _subscribers_lock:
        _subscribers.append(q)
    return Response(
        _sse_stream(q),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.route("/api/ping")
def ping():
    return jsonify({"ok": True, "subscribers": len(_subscribers)})


# ── 启动 ─────────────────────────────────────────────────────
if __name__ == "__main__":
    import socket

    def _local_ip():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    ip = _local_ip()
    port = int(os.environ.get("PORT", 8766))
    print("=" * 55)
    print("  结算工作台 Entity 版 · 局域网协作服务")
    print("=" * 55)
    print(f"  本机访问:   http://localhost:{port}")
    print(f"  局域网访问: http://{ip}:{port}   ← 发给同事")
    print(f"  状态文件:   {STATE_FILE}")
    print("=" * 55)
    app.run(host="0.0.0.0", port=port, threaded=True, debug=False)
