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

app = Flask(__name__)
dotenv.load_dotenv()

# ================= CONFIG =================

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
    print(f"Error initializing API: {e}")
    api = None


# ================= TELEGRAM FUNCTIONS =================

def send_telegram_queue(username, client_id, position, total_queue):
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not bot_token or not chat_id:
        return

    message = (
        "📥 <b>New Queue Request</b>\n\n"
        f"👤 User: {username}\n"
        f"🆔 Client ID: <code>{client_id}</code>\n"
        f"📊 Queue: {position}/{total_queue}\n"
        f"⏰ Time: {time.strftime('%Y-%m-%d %H:%M:%S')}"
    )

    try:
        requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"},
            timeout=10
        )
    except Exception as e:
        print("Telegram queue notify failed:", e)


def send_telegram_processing(username, client_id):
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not bot_token or not chat_id:
        return

    message = (
        "⚙️ <b>Processing Started</b>\n\n"
        f"👤 User: {username}\n"
        f"🆔 Client ID: <code>{client_id}</code>\n"
        f"⏰ Start: {time.strftime('%Y-%m-%d %H:%M:%S')}"
    )

    try:
        requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"},
            timeout=10
        )
    except Exception as e:
        print("Telegram processing notify failed:", e)


def send_telegram_error(username, client_id, error):
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not bot_token or not chat_id:
        return

    message = (
        "❌ <b>Restore Failed</b>\n\n"
        f"👤 User: {username}\n"
        f"🆔 Client ID: <code>{client_id}</code>\n"
        f"⚠️ Error:\n<pre>{error}</pre>\n"
        f"⏰ Time: {time.strftime('%Y-%m-%d %H:%M:%S')}"
    )

    try:
        requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"},
            timeout=10
        )
    except Exception as e:
        print("Telegram error notify failed:", e)


def send_telegram_notification(username, uid, product_id, raw_json):
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not bot_token or not chat_id:
        return

    subscription_info = json.dumps(
        raw_json.get("subscriber", {}).get("entitlements", {}).get("Gold", {}),
        indent=2
    )

    message = (
        "✅ <b>Locket Gold Unlocked!</b>\n\n"
        f"👤 User: {username} ({uid})\n"
        f"📦 Product: {product_id}\n"
        f"⏰ Time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        f"<b>Subscription Info:</b>\n<pre>{subscription_info}</pre>"
    )

    try:
        requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"},
            timeout=10
        )
    except Exception as e:
        print("Telegram success notify failed:", e)


# ================= QUEUE MANAGER =================

class QueueManager:
    def __init__(self):
        self.queue = queue.Queue()
        self.lock = threading.Lock()
        self.client_requests = {}
        self.processing_times = []
        self.current_processing = None

        self.worker_thread = threading.Thread(
            target=self._process_queue,
            daemon=True
        )
        self.worker_thread.start()

        print("Queue manager initialized")

    def add_to_queue(self, username):
        client_id = str(uuid.uuid4())
        with self.lock:
            self.client_requests[client_id] = {
                "username": username,
                "status": "waiting",
                "result": None,
                "error": None,
                "added_at": datetime.now(),
                "started_at": None,
                "completed_at": None,
            }

        self.queue.put(client_id)
        return client_id

    def get_status(self, client_id):
        with self.lock:
            if client_id not in self.client_requests:
                return None

            data = self.client_requests[client_id].copy()

        position = self._get_position(client_id)
        total_queue = self.queue.qsize()
        if self.current_processing and self.current_processing != client_id:
            total_queue += 1

        return {
            "client_id": client_id,
            "status": data["status"],
            "position": position,
            "total_queue": total_queue,
            "estimated_time": self._estimate_wait_time(position),
            "result": data["result"],
            "error": data["error"],
        }

    def _get_position(self, client_id):
        if self.current_processing == client_id:
            return 0
        q = list(self.queue.queue)
        return q.index(client_id) + 1 if client_id in q else 0

    def _estimate_wait_time(self, position):
        if position == 0:
            return 0
        avg = (
            sum(self.processing_times[-10:]) / len(self.processing_times[-10:])
            if self.processing_times else 5
        )
        return int(position * avg)

    def _process_queue(self):
        while True:
            try:
                client_id = self.queue.get(timeout=1)

                with self.lock:
                    if client_id not in self.client_requests:
                        continue

                    self.current_processing = client_id
                    self.client_requests[client_id]["status"] = "processing"
                    self.client_requests[client_id]["started_at"] = datetime.now()
                    username = self.client_requests[client_id]["username"]

                send_telegram_processing(username, client_id)

                self._process_request(client_id)

                with self.lock:
                    self.current_processing = None
                    self.client_requests[client_id]["completed_at"] = datetime.now()

                self.queue.task_done()

            except queue.Empty:
                continue

    def _process_request(self, client_id):
        try:
            with self.lock:
                username = self.client_requests[client_id]["username"]

            account_info = api.getUserByUsername(username)
            user_data = account_info["result"]["data"]
            uid = user_data["uid"]

            restore_result = api.restorePurchase(uid)
            gold = restore_result.get("subscriber", {}).get("entitlements", {}).get("Gold", {})

            if gold.get("product_identifier") in subscription_ids:
                send_telegram_notification(
                    username,
                    uid,
                    gold.get("product_identifier"),
                    restore_result
                )
                with self.lock:
                    self.client_requests[client_id]["status"] = "completed"
                    self.client_requests[client_id]["result"] = {"success": True}
            else:
                raise Exception("Gold entitlement not found")

        except Exception as e:
            send_telegram_error(username, client_id, str(e))
            with self.lock:
                self.client_requests[client_id]["status"] = "error"
                self.client_requests[client_id]["error"] = str(e)


queue_manager = QueueManager()


# ================= FLASK ROUTES =================

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/restore", methods=["POST"])
def restore_purchase():
    username = request.json.get("username")
    client_id = queue_manager.add_to_queue(username)
    status = queue_manager.get_status(client_id)

    send_telegram_queue(
        username,
        client_id,
        status["position"],
        status["total_queue"]
    )

    return jsonify({"success": True, **status})


@app.route("/api/queue/status", methods=["POST"])
def queue_status():
    client_id = request.json.get("client_id")
    status = queue_manager.get_status(client_id)
    return jsonify({"success": True, **status})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
