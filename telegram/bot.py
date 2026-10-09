import logging
import os
import requests

from config import Config


class Telegram:
    """Telegram transport with fail-closed sender allowlisting."""

    def __init__(self):
        self.token = Config.TELEGRAM_BOT_TOKEN
        self.chat_id = Config.TELEGRAM_CHAT_ID
        self.last_update_id = 0
        raw_ids = os.getenv("TELEGRAM_ALLOWED_USER_IDS", "").strip()
        self.allowed_user_ids = {
            item.strip() for item in raw_ids.split(",") if item.strip()
        }

    def _authorized(self, user_id):
        return bool(self.allowed_user_ids) and str(user_id or "") in self.allowed_user_ids

    def send(self, text, keyboard=None):
        if not self.token or not self.chat_id:
            logging.warning("Telegram credentials missing.")
            return False
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {"chat_id": self.chat_id, "text": text}
        if keyboard:
            payload["reply_markup"] = {"inline_keyboard": keyboard}
        try:
            response = requests.post(url, json=payload, timeout=10)
            if not response.ok:
                logging.error("Telegram send failed: %s", response.text)
                return False
            return True
        except Exception:
            logging.exception("Telegram send error")
            return False

    def mode_keyboard(self, current_mode):
        if current_mode == "AUTO":
            return [[
                {"text": "🟢 AUTO MODE", "callback_data": "mode_auto"},
                {"text": "🔴 Switch to MANUAL", "callback_data": "mode_manual"},
            ]]
        return [[
            {"text": "🟢 Switch to AUTO", "callback_data": "mode_auto"},
            {"text": "🔴 MANUAL MODE", "callback_data": "mode_manual"},
        ]]

    def send_mode_panel(self, current_mode):
        text = (
            "🤖 Trading Bot Control\n\n"
            f"Current Mode: {current_mode}\n\n"
            "AUTO = requests automatic evaluation; actual order submission "
            "remains disabled in execution.py.\n"
            "MANUAL = signals only, no automatic orders."
        )
        return self.send(text, self.mode_keyboard(current_mode))

    def poll(self):
        if not self.token:
            return []
        if not self.allowed_user_ids:
            logging.error("Telegram polling disabled: TELEGRAM_ALLOWED_USER_IDS is empty.")
            return []
        url = f"https://api.telegram.org/bot{self.token}/getUpdates"
        try:
            response = requests.get(
                url,
                params={"offset": self.last_update_id + 1, "timeout": 1},
                timeout=5,
            )
            response.raise_for_status()
            data = response.json()
            if not data.get("ok"):
                return []
            updates = data.get("result", [])
            if updates:
                self.last_update_id = updates[-1]["update_id"]
            accepted = []
            for update in updates:
                if "message" in update:
                    user_id = (update["message"].get("from") or {}).get("id")
                elif "callback_query" in update:
                    user_id = (update["callback_query"].get("from") or {}).get("id")
                else:
                    user_id = None
                if self._authorized(user_id):
                    accepted.append(update)
                else:
                    logging.warning("Dropped unauthorized Telegram update.")
            return accepted
        except Exception:
            logging.exception("Telegram poll error")
            return []

    def answer_callback(self, callback_query_id):
        if not self.token or not callback_query_id:
            return False
        url = f"https://api.telegram.org/bot{self.token}/answerCallbackQuery"
        try:
            response = requests.post(
                url, json={"callback_query_id": callback_query_id}, timeout=5
            )
            return bool(response.ok)
        except Exception:
            logging.exception("Telegram callback response error")
            return False
