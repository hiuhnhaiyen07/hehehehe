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

# ================== BASIC SETUP ==================

dotenv.load_dotenv()
app = Flask(__name__)

def get_client_ip(req):
    if req.headers.get("X-Forwarded-For"):
        return req.headers.get("X-Forwarded-For").split(",")[0]
    return req.remote_addr

# ================== AUTH & API ==================

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

# ================== TELEGRAM ==================

def send_telegram_notification(username, uid, ip, status, client_id, note=None):
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not bot_token or not chat_id:
        return

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    icon = {
        "waiting": "⏳",
        "processing": "⚙️",
        "completed": "✅",
        "error": "❌",
    }.get(status, "ℹ️")

    message = f"""
<b>🔔 LOCKET SYSTEM</b>

👤 <b>Username:</b> <code>{username}</code>
🆔 <b>UID:</b> <code>{uid or "N/A"}</code>
🌐 <b>IP:</b> <code>{ip}</code>

📌 <b>Status:</b> {icon} <b>{status.upper()}</b>
🆔 <b>Client ID:</b>
<code>{client_id}</code>

⏰ <b>Time:</b> {now}
"""

    if note:
        message += f"\n📝 <b>Note:</b>\n<pre>{note}</pre>"

    requests.post(
        f"https://api.telegram.org/bot{bot_token}/sendMessage",
        json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"},
        timeout=10
    )

# ================== QUEUE MANAGER ==================

class QueueManager:
    def __init__(self):
        self.queue = queue.Queue()
        self.lock = threading.Lock()
        self.client_requests = {}
        self.current_processing = None
        threading.Thread(target=self._process_queue, daemon=True).start()

    def add_to_queue(self, username, ip):
        client_id = str(uuid.uuid4())
        self.client_requests[client_id] = {
            "username": username,
            "ip": ip,
            "status": "waiting",
        }
        self.queue.put(client_id)
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
            try:
                client_id = self.queue.get()
                self.current_processing = client_id
                data = self.client_requests[client_id]
                data["status"] = "processing"

                send_telegram_notification(
                    data["username"], None, data["ip"],
                    "processing", client_id
                )

                self._process_request(client_id)

                self.queue.task_done()
            except Exception as e:
                print("QUEUE ERROR:", e)

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
                data["status"] = "completed"
                send_telegram_notification(
                    username, uid, data["ip"],
                    "completed", client_id,
                    f"Unlocked {gold.get('product_identifier')}"
                )
            else:
                raise Exception("Gold entitlement not found")

        except Exception as e:
            data["status"] = "error"
            send_telegram_notification(
                username, None, data["ip"],
                "error", client_id, str(e)
            )

# ================== ROUTES ==================

queue_manager = QueueManager()

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/restore", methods=["POST"])
def restore():
    if not api:
        return jsonify({"success": False, "msg": "API not ready"}), 500

    data = request.json
    username = data.get("username")
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

# ================== RUN ==================

if __name__ == "__main__":
    app.run(debug=True, port=5000)             raise e

        # Check if we got a valid response structure
        if not account_info or "result" not in account_info:
            return jsonify(
                {"success": False, "msg": "User not found or API error"}
            ), 404

        user_data = account_info.get("result", {}).get("data")
        if not user_data:
            return jsonify({"success": False, "msg": "User data not found"}), 404

        # Extract relevant user information
        user_info = {
            "uid": user_data.get("uid"),
            "username": user_data.get("username"),
            "first_name": user_data.get("first_name", ""),
            "last_name": user_data.get("last_name", ""),
            "profile_picture_url": user_data.get("profile_picture_url", ""),
        }

        return jsonify({"success": True, "data": user_info})

    except Exception as e:
        print(f"Error in get user info: {e}")
        return jsonify({"success": False, "msg": f"An error occurred: {str(e)}"}), 500


def send_telegram_notification(username, uid, product_id, raw_json):
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if bot_token == "" or chat_id == "":
        print("Telegram notification skipped: Token or Chat ID not set.")
        return
    subscription_info = json.dumps(
        raw_json.get("subscriber", {}).get("entitlements", {}).get("Gold", {}), indent=2
    )

    message = f"✅ <b>Locket Gold Unlocked!</b>\n\n👤 <b>User:</b> {username} ({uid})\n⏰ <b>Time:</b> {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n<b>Subscription Info:</b>\n<pre>{subscription_info}</pre>"
    # send file json
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}

    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Failed to send Telegram notification: {e}")


@app.route("/api/restore", methods=["POST"])
def restore_purchase():
    """Add request to queue and return client_id for tracking"""
    if not api:
        return jsonify(
            {"success": False, "msg": "API not initialized. Check server logs."}
        ), 500

    data = request.json
    username = data.get("username")

    if not username:
        return jsonify({"success": False, "msg": "Username is required"}), 400

    try:
        # Add to queue
        client_id = queue_manager.add_to_queue(username)

        # Get initial status
        status = queue_manager.get_status(client_id)

        return jsonify(
            {
                "success": True,
                "client_id": client_id,
                "position": status["position"],
                "total_queue": status["total_queue"],
                "estimated_time": status["estimated_time"],
            }
        )

    except Exception as e:
        print(f"Error adding to queue: {e}")
        return jsonify({"success": False, "msg": f"An error occurred: {str(e)}"}), 500


@app.route("/api/queue/status", methods=["POST"])
def queue_status():
    """Get current queue status for a client"""
    data = request.json
    client_id = data.get("client_id")

    if not client_id:
        return jsonify({"success": False, "msg": "client_id is required"}), 400

    status = queue_manager.get_status(client_id)

    if status is None:
        return jsonify({"success": False, "msg": "Client ID not found"}), 404

    return jsonify({"success": True, **status})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
