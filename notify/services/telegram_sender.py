import os
import mimetypes
import requests
from django.conf import settings

# =========================
# Telegram Config
# =========================

BOT_TOKEN = getattr(settings, "TELEGRAM_BOT_TOKEN", "")

BASE_URL = (
    f"https://api.telegram.org/bot{BOT_TOKEN}"
    if BOT_TOKEN
    else None
)

DEFAULT_MESSAGE = "📢 คุณมีการแจ้งเตือนใหม่"


# =========================
# Main Sender
# =========================

def send_telegram_message(notification) -> bool:
    if not BOT_TOKEN or not BASE_URL:
        print("[TG] ❌ Missing BOT_TOKEN")
        return False

    user = notification.user
    if not user.telegram_chat_id:
        print("[TG] ❌ Missing chat_id")
        return False

    message_text = notification.description or ""

    try:
        resp = requests.post(
            f"{BASE_URL}/sendMessage",
            json={
                "chat_id": user.telegram_chat_id,
                "text": message_text,
            },
            timeout=10,
        )

        print("[TG] status:", resp.status_code)
        print("[TG] response:", resp.text)

        if resp.status_code != 200:
            return False

        # ส่งไฟล์ (ถ้ามี)
        if notification.file:
            file_ok = send_file(notification, user.telegram_chat_id)
            if not file_ok:
                print("[TG] ❌ File send failed")
                return False

        print("[TG] ✅ Sent successfully")
        return True

    except Exception as e:
        print("[TG] ❌ Exception:", str(e))
        return False



# =========================
# Send Helpers
# =========================

def send_text(chat_id: str, text: str) -> bool:
    response = requests.post(
        f"{BASE_URL}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": text,
        },
        timeout=10,
    )
    return response.status_code == 200


def send_file(chat_id: str, file_path: str, caption: str = "") -> bool:
    """
    ส่งไฟล์ไป Telegram
    - image → sendPhoto
    - อื่น ๆ → sendDocument
    """

    mime_type, _ = mimetypes.guess_type(file_path)
    filename = os.path.basename(file_path)

    if mime_type and mime_type.startswith("image"):
        endpoint = "sendPhoto"
        file_key = "photo"
    else:
        endpoint = "sendDocument"
        file_key = "document"

    with open(file_path, "rb") as f:
        files = {
            file_key: (filename, f)
        }
        data = {
            "chat_id": chat_id,
            "caption": caption,
        }

        response = requests.post(
            f"{BASE_URL}/{endpoint}",
            data=data,
            files=files,
            timeout=20,
        )

    return response.status_code == 200
