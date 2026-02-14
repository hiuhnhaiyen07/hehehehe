from flask import Flask, render_template, request, jsonify
from auth import Auth
from api import LocketAPI
import json
import time
import requests
import queue
import threading
import uuid
from datetime import datetime
import dotenv
import os

# ===================== BASIC =====================

dotenv.load_dotenv()
app = Flask(__name__)

def get_client_ip(req):
    if req.headers.get("X-Forwarded-For"):
        return req.headers.get("X-Forwarded-For").split(",")[0]
    return req.remote_addr

# ===================== AUTH & API =====================

subscription_ids = [
    "locket_1600_1y",
    "locket_199_1m",
    "locket_199_1m_only",
    "locket_3600_1y",
    "locket_399_1m_only",
]

auth = Auth(os.getenv("EMAIL"), os.getenv("PASSWORD"))

try:
    token = auth.get_token()
    api = LocketAPI(token)
except Exception as e:
    print("API INIT ERROR:", e)
    api = None

def refresh_api_token():
    global api
    try:
        new_token = auth.create_token()
        api = LocketAPI(new_token)
        return True
    except Exception as e:
        print("TOKEN REFRESH ERROR:", e)
        return False

# ===================== TELEGRAM BOT =====================

def send_telegram_notification(
    username,
    status,
    client_id,
    ip=None,
    uid=None,
    note=None,
    raw_json=None
):
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not bot_token or not chat_id:
        return

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    ICON = {
        "queued": "📥",
        "processing": "⚙️",
        "success": "✅",
        "error": "❌",
    }.get(status, "ℹ️")

    message = f"""
<b>🔔 LOCKET SYSTEM</b>

👤 <b>User:</b> <code>{username}</code>
🆔 <b>UID:</b> <code>{uid or 'N/A'}</code>
🌐 <b>IP:</b> <code>{ip or 'N/A'}</code>

📌 <b>Status:</b> {ICON} <b>{status.upper()}</b>
🆔 <b>Client ID:</b>
<code>{client_id}</code>

⏰ <b>Time:</b> {now}
"""

    if note:
        message += f"\n📝 <b>Note:</b>\n<pre>{note}</pre>"

    requests.post(
        f"https://api.telegram.org/bot{bot_token}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        },
        timeout=10
    )

    if raw_json:
        files = {
            "document": (
                f"{username}_{client_id}.json",
                json.dumps(raw_json, indent=2),
                "application/json"
            )
        }
        requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendDocument",
            data={"chat_id": chat_id},
            files=files,
            timeout=10
        )

# ===================== QUEUE SYSTEM =====================

class QueueManager:
    def __init__(self):
        self.queue = queue.Queue()
        self.lock = threading.Lock()
        self.client_requests = {}
        threading.Thread(target=self._process_queue, daemon=True).start()
        print("Queue worker started")

    def add_to_queue(self, username, ip):
        client_id = str(uuid.uuid4())
        self.client_requests[client_id] = {
            "username": username,
            "ip": ip,
            "status": "queued"
        }
        self.queue.put(client_id)

        send_telegram_notification(
            username=username,
            status="queued",
            client_id=client_id,
            ip=ip
        )

        return client_id

    def get_status(self, client_id):
        if client_id not in self.client_requests:
            return None
        return {
            "status": self.client_requests[client_id]["status"],
            "position": list(self.queue.queue).index(client_id) + 1
            if client_id in self.queue.queue else 0
        }

    def _process_queue(self):
        while True:
            client_id = self.queue.get()
            data = self.client_requests.get(client_id)
            if not data:
                continue

            data["status"] = "processing"
            send_telegram_notification(
                username=data["username"],
                status="processing",
                client_id=client_id,
                ip=data["ip"]
            )

            self._process_request(client_id)
            self.queue.task_done()

    def _process_request(self, client_id):
        data = self.client_requests[client_id]
        username = data["username"]

        try:
            try:
                account_info = api.getUserByUsername(username)
            except Exception:
                refresh_api_token()
                account_info = api.getUserByUsername(username)

            user_data = account_info["result"]["data"]
            uid = user_data["uid"]

            try:
                restore = api.restorePurchase(uid)
            except Exception:
                refresh_api_token()
                restore = api.restorePurchase(uid)

            entitlements = restore.get("subscriber", {}).get("entitlements", {})
            gold = entitlements.get("Gold", {})

            if gold.get("product_identifier") in subscription_ids:
                data["status"] = "success"
                send_telegram_notification(
                    username=username,
                    status="success",
                    client_id=client_id,
                    uid=uid,
                    ip=data["ip"],
                    note=f"Unlocked {gold.get('product_identifier')}",
                    raw_json=restore
                )
            else:
                raise Exception("Gold entitlement not found")

        except Exception as e:
            data["status"] = "error"
            send_telegram_notification(
                username=username,
                status="error",
                client_id=client_id,
                ip=data["ip"],
                note=str(e)
            )

# ===================== ROUTES =====================

queue_manager = QueueManager()

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/restore", methods=["POST"])
def restore():
    if not api:
        return jsonify({"success": False, "msg": "API not ready"}), 500

    username = request.json.get("username")
    if not username:
        return jsonify({"success": False, "msg": "Username required"}), 400

    ip = get_client_ip(request)
    client_id = queue_manager.add_to_queue(username, ip)

    return jsonify({
        "success": True,
        "client_id": client_id
    })

@app.route("/api/queue/status", methods=["POST"])
def queue_status():
    client_id = request.json.get("client_id")
    status = queue_manager.get_status(client_id)
    if not status:
        return jsonify({"success": False}), 404
    return jsonify({"success": True, **status})

# ===================== RUN =====================

if __name__ == "__main__":
    app.run(debug=True, port=5000)
