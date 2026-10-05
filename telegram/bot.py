import logging
import requests

from config import Config


class Telegram:

    def __init__(self):
        self.token = Config.TELEGRAM_BOT_TOKEN
        self.chat_id = Config.TELEGRAM_CHAT_ID
        self.last_update_id = 0

    # ========================================================
    # SEND MESSAGE
    # ========================================================

    def send(self, text, keyboard=None):
        if not self.token or not self.chat_id:
            logging.warning("Telegram credentials missing.")
            return False

        url = f"https://api.telegram.org/bot{self.token}/sendMessage"

        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "Markdown"
        }

        if keyboard:
            payload["reply_markup"] = {
                "inline_keyboard": keyboard
            }

        try:
            response = requests.post(
                url,
                json=payload,
                timeout=10
            )

            if not response.ok:
                logging.error(
                    f"Telegram send failed: {response.text}"
                )
                return False

            return True

        except Exception as e:
            logging.error(
                f"Telegram send error: {e}"
            )
            return False

    # ========================================================
    # MODE CONTROL
    # ========================================================

    def mode_keyboard(self, current_mode):
        if current_mode == "AUTO":
            return [
                [
                    {
                        "text": "🟢 AUTO MODE",
                        "callback_data": "mode_auto"
                    },
                    {
                        "text": "🔴 Switch to MANUAL",
                        "callback_data": "mode_manual"
                    }
                ]
            ]

        return [
            [
                {
                    "text": "🟢 Switch to AUTO",
                    "callback_data": "mode_auto"
                },
                {
                    "text": "🔴 MANUAL MODE",
                    "callback_data": "mode_manual"
                }
            ]
        ]

    def send_mode_panel(self, current_mode):
        text = (
            "🤖 *Trading Bot Control*\n\n"
            f"Current Mode: *{current_mode}*\n\n"
            "🟢 AUTO = automatic execution enabled\n"
            "🔴 MANUAL = signals only, no automatic orders"
        )

        return self.send(
            text,
            self.mode_keyboard(current_mode)
        )

    # ========================================================
    # GET UPDATES
    # ========================================================

    def poll(self):
        if not self.token:
            return []

        url = f"https://api.telegram.org/bot{self.token}/getUpdates"

        try:
            response = requests.get(
                url,
                params={
                    "offset": self.last_update_id + 1,
                    "timeout": 1
                },
                timeout=5
            )

            data = response.json()

            if not data.get("ok"):
                return []

            updates = data.get("result", [])

            if updates:
                self.last_update_id = updates[-1]["update_id"]

            return updates

        except Exception as e:
            logging.error(
                f"Telegram poll error: {e}"
            )
            return []

    # ========================================================
    # CALLBACK RESPONSE
    # ========================================================

    def answer_callback(self, callback_query_id):
        if not self.token:
            return False

        url = (
            f"https://api.telegram.org/"
            f"bot{self.token}/answerCallbackQuery"
        )

        try:
            requests.post(
                url,
                json={
                    "callback_query_id": callback_query_id
                },
                timeout=5
            )

            return True

        except Exception as e:
            logging.error(
                f"Telegram callback error: {e}"
            )
            return False
