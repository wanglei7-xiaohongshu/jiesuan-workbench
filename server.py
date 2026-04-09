#!/usr/bin/env python3
"""
结算工作台 - 公网协作服务（带密码 + 免密 Token）
用法:
    pip install flask flask-cors
    python3 server.py
访问: http://<公网IP>:8765
免密链接: http://<公网IP>:8765/?token=jiesuan-free-2026
"""

import json
import os
import queue
import threading
from functools import wraps
from pathlib import Path

from flask import Flask, Response, jsonify, redirect, request, send_from_directory, session
from flask_cors import CORS

app = Flask(__name__, static_folder=".")
app.secret_key = "jiesuan-secret-key-workbench-2026"
CORS(app)

# ── 认证配置 ─────────────────────────────────────────────────
PASSWORD = "techchangeworld"
FREE_TOKEN = "jiesuan-free-2026"          # 免密 token（结算工作台）

# ── 数据持久化路径 ────────────────────────────────────────────
STATE_FILE = Path(__file__).parent / "workbench_state.json"

# ── SSE 广播 ─────────────────────────────────────────────────
_subscribers: list[queue.Queue] = []
_subscribers_lock = threading.Lock()


def _broadcast(event_type: str, data: str = "{}"):
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


# ── 认证检查 ─────────────────────────────────────────────────
def _is_authed() -> bool:
    """检查当前请求是否已认证（session 登录 或 token 参数）。"""
    if request.args.get("token") == FREE_TOKEN:
        return True
    if session.get("authed"):
        return True
    return False


def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not _is_authed():
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated


# ── 登录页 ────────────────────────────────────────────────────
LOGIN_HTML = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>结算工作台 · 登录</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { min-height: 100vh; display: flex; align-items: center; justify-content: center;
         background: #f0f2f5; font-family: -apple-system, BlinkMacSystemFont, sans-serif; }
  .card { background: #fff; padding: 40px; border-radius: 12px; box-shadow: 0 4px 24px rgba(0,0,0,.1);
          width: 340px; text-align: center; }
  h2 { font-size: 22px; margin-bottom: 8px; color: #1a1a1a; }
  p { color: #888; font-size: 14px; margin-bottom: 28px; }
  input { width: 100%; padding: 12px 16px; border: 1px solid #ddd; border-radius: 8px;
          font-size: 15px; outline: none; transition: border .2s; }
  input:focus { border-color: #4f8ef7; }
  button { margin-top: 16px; width: 100%; padding: 12px; background: #4f8ef7; color: #fff;
           border: none; border-radius: 8px; font-size: 15px; cursor: pointer; transition: background .2s; }
  button:hover { background: #3a7ce0; }
  .error { margin-top: 14px; color: #e53e3e; font-size: 13px; }
</style>
</head>
<body>
<div class="card">
  <h2>结算工作台</h2>
  <p>请输入访问密码</p>
  <form method="post" action="/login">
    <input type="password" name="password" placeholder="密码" autofocus>
    <button type="submit">进入</button>
    {error}
  </form>
</div>
</body>
</html>"""


@app.route("/login", methods=["GET"])
def login_page():
    return LOGIN_HTML.replace("{error}", ""), 200


@app.route("/login", methods=["POST"])
def login_post():
    pwd = request.form.get("password", "")
    if pwd == PASSWORD:
        session["authed"] = True
        return redirect("/")
    return LOGIN_HTML.replace("{error}", '<div class="error">密码错误，请重试</div>'), 401


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


# ── 主路由 ────────────────────────────────────────────────────
@app.route("/")
@require_auth
def index():
    # 如果带 token 参数，保持 token 透传给 API 请求
    return send_from_directory(".", "结算工作台.html")


@app.route("/api/state", methods=["GET"])
@require_auth
def get_state():
    return jsonify(_load_state())


@app.route("/api/state", methods=["POST"])
@require_auth
def post_state():
    data = request.get_json(force=True, silent=True)
    if data is None:
        return jsonify({"error": "invalid json"}), 400
    _save_state(data)
    _broadcast("state_updated")
    return jsonify({"ok": True})


@app.route("/api/events")
@require_auth
def sse_events():
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
    port = int(os.environ.get("PORT", 8765))
    print("=" * 60)
    print("  结算工作台 · 公网服务")
    print("=" * 60)
    print(f"  普通访问:   http://{ip}:{port}  （需要密码）")
    print(f"  免密链接:   http://{ip}:{port}/?token={FREE_TOKEN}")
    print(f"  状态文件:   {STATE_FILE}")
    print("=" * 60)
    app.run(host="0.0.0.0", port=port, threaded=True, debug=False)
