import hashlib
import hmac
import json
import logging
import os
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import telebot
from telebot.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    WebAppInfo,
)

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("renova-bots")

# Telegram bot configuration
RENOVA_TOKEN = os.getenv("RENOVA_BOT_TOKEN")
NERO_TOKEN = os.getenv("NERO_BOT_TOKEN")
CLAIR_TOKEN = os.getenv("CLAIR_BOT_TOKEN")
CLAIR_ADMIN_ID = int(os.getenv("CLAIR_ADMIN_ID", "8664218481"))
CLAIR_ADMIN_USERNAME = "renovaaetherstone"

WEBSITE_URL = "https://www.renovaaetherandstone.com"
TEXT_URL = "https://square.link/u/yaq743A5"
VOICE_URL = "https://square.link/u/oYibDkgK"
CLAIR_URL = "https://t.me/ClairAetherBot?start=renova"
TELEGRAM_GROUP_URL = "https://t.me/+3ClNaQ3t5KJjZTJl"
WHATSAPP_GROUP_URL = "https://chat.whatsapp.com/LTIVL6u2QFl3zEzX2ARKNE"

# WhatsApp Cloud API configuration. Set secrets only in Railway variables.
WHATSAPP_GRAPH_VERSION = os.getenv("WHATSAPP_GRAPH_VERSION", "v26.0")
WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "")
WHATSAPP_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN", "")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
META_APP_SECRET = os.getenv("META_APP_SECRET", "")

SESSIONS = {}
# Maps a forwarded WhatsApp message in Jarrod's private Clair chat to the
# originating WhatsApp number. The `/wa` command remains available if the
# service restarts before Jarrod replies to an older forwarded message.
WHATSAPP_REPLY_TARGETS = {}
renova_bot = telebot.TeleBot(RENOVA_TOKEN) if RENOVA_TOKEN else None
nero_bot = telebot.TeleBot(NERO_TOKEN) if NERO_TOKEN else None
clair_bot = telebot.TeleBot(CLAIR_TOKEN) if CLAIR_TOKEN else None


# ---------------------------------------------------------------------------
# Telegram storefront and Clair intake flow
# ---------------------------------------------------------------------------
def customer_menu():
    menu = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    menu.add(
        KeyboardButton("🔮 3-Question Text Reading"),
        KeyboardButton("🎙️ 15-Minute Voice Note"),
    )
    menu.add(KeyboardButton("🌐 Renova Website"), KeyboardButton("❓ Help"))
    return menu


def admin_menu():
    menu = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    menu.add(KeyboardButton("📜 New Reading Requests"), KeyboardButton("🕯 Reading Status"))
    menu.add(KeyboardButton("🌙 Test Customer Flow"), KeyboardButton("💬 Main Menu"))
    return menu


def reading_options():
    menu = InlineKeyboardMarkup(row_width=1)
    menu.add(
        InlineKeyboardButton("🔮 3-Question Text Reading — $25 AUD", callback_data="renova_text"),
        InlineKeyboardButton("🎙️ 15-Minute Voice Note — $50 AUD", callback_data="renova_voice"),
        InlineKeyboardButton("🏠 Main Menu", callback_data="renova_main"),
    )
    return menu


def renova_menu():
    menu = InlineKeyboardMarkup(row_width=1)
    menu.add(
        InlineKeyboardButton("📜 Book a Reading", callback_data="renova_readings"),
        InlineKeyboardButton("🔮 About Jarrod & Practice", callback_data="renova_about"),
        InlineKeyboardButton("📖 Telegram Insights Group", url=TELEGRAM_GROUP_URL),
        InlineKeyboardButton("💬 WhatsApp Insights Community", url=WHATSAPP_GROUP_URL),
        InlineKeyboardButton("📞 Contact / PayID", callback_data="renova_contact"),
        InlineKeyboardButton("🌐 Open Interactive Site", web_app=WebAppInfo(url=WEBSITE_URL)),
    )
    return menu


if renova_bot:
    @renova_bot.message_handler(commands=["start", "menu"])
    def renova_start(message):
        renova_bot.send_message(
            message.chat.id,
            "✨ **Welcome to Renova Aether & Stone** ✨\n\n"
            "A grounded space for intuitive listening, tarot, geographic energy and thoughtful reflection.",
            reply_markup=renova_menu(),
            parse_mode="Markdown",
        )


    @renova_bot.callback_query_handler(func=lambda call: call.data.startswith("renova_"))
    def renova_callbacks(call):
        if call.data == "renova_readings":
            text = (
                "✨ **CHOOSE YOUR READING FORMAT** ✨\n\n"
                "Select your reading below. After choosing, Renova will show the correct payment link "
                "and remind you to continue with Clair — RAS."
            )
            menu = reading_options()
        elif call.data == "renova_text":
            text = (
                "🔮 **3-QUESTION TEXT READING — $25 AUD**\n\n"
                "Please complete payment, then return here and tap **Continue with Clair — RAS**. "
                "Clair will collect your three questions and send them to Jarrod."
            )
            menu = InlineKeyboardMarkup(row_width=1)
            menu.add(
                InlineKeyboardButton("💳 Pay $25 AUD", url=TEXT_URL),
                InlineKeyboardButton("🌙 Continue with Clair — RAS", url=CLAIR_URL),
                InlineKeyboardButton("🏠 Main Menu", callback_data="renova_main"),
            )
        elif call.data == "renova_voice":
            text = (
                "🎙️ **15-MINUTE VOICE NOTE READING — $50 AUD**\n\n"
                "Please complete payment, then return here and tap **Continue with Clair — RAS**. "
                "Clair will collect your voice-note request and send it to Jarrod."
            )
            menu = InlineKeyboardMarkup(row_width=1)
            menu.add(
                InlineKeyboardButton("💳 Pay $50 AUD", url=VOICE_URL),
                InlineKeyboardButton("🌙 Continue with Clair — RAS", url=CLAIR_URL),
                InlineKeyboardButton("🏠 Main Menu", callback_data="renova_main"),
            )
        elif call.data == "renova_about":
            text = (
                "🔮 **ABOUT JARROD & RENOVA AETHER & STONE**\n\n"
                "A reading practice rooted in intuitive listening, tarot, geographic energy and grounded reflection."
            )
            menu = InlineKeyboardMarkup(row_width=1)
            menu.add(
                InlineKeyboardButton("📜 View Readings & Pricing", callback_data="renova_readings"),
                InlineKeyboardButton("🔙 Back to Main Menu", callback_data="renova_main"),
            )
        elif call.data == "renova_contact":
            text = "💬 **CONTACT & DIRECT PAYMENT**\n\nPayID: `+61479129590`"
            menu = InlineKeyboardMarkup(row_width=1)
            menu.add(
                InlineKeyboardButton("📖 Telegram Insights Group", url=TELEGRAM_GROUP_URL),
                InlineKeyboardButton("💬 WhatsApp Community", url=WHATSAPP_GROUP_URL),
                InlineKeyboardButton("🔙 Back to Main Menu", callback_data="renova_main"),
            )
        else:
            text = "✨ **Welcome to Renova Aether & Stone** ✨\n\nChoose an option below, and let’s see what is already speaking."
            menu = renova_menu()

        renova_bot.answer_callback_query(call.id)
        renova_bot.edit_message_text(
            text=text,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=menu,
            parse_mode="Markdown",
        )


if nero_bot:
    @nero_bot.message_handler(commands=["start"])
    def nero_start(message):
        menu = InlineKeyboardMarkup()
        menu.add(InlineKeyboardButton("🧪 Test Webview", web_app=WebAppInfo(url=WEBSITE_URL)))
        nero_bot.send_message(message.chat.id, "🧪 **Nero Sandbox Active**", reply_markup=menu, parse_mode="Markdown")


if clair_bot:
    def is_clair_admin(user):
        return user.id == CLAIR_ADMIN_ID or (user.username or "").lower() == CLAIR_ADMIN_USERNAME


    @clair_bot.message_handler(commands=["start", "menu"])
    def clair_start(message):
        if is_clair_admin(message.from_user):
            clair_bot.send_message(
                message.chat.id,
                "🌙 **Welcome back, Jarrod.**\n\nWhat whispers do we have today?",
                reply_markup=admin_menu(),
                parse_mode="Markdown",
            )
        else:
            clair_bot.send_message(
                message.chat.id,
                "🌙 **Welcome to Clair — RAS.**\n\n"
                "I’m Renova’s reading companion, and I’ll help gather your questions or voice-note request for Jarrod.\n\n"
                "Choose your reading path below when you’re ready.",
                reply_markup=customer_menu(),
                parse_mode="Markdown",
            )


    def _send_clair_whatsapp_reply(message, recipient, body):
        if not recipient or not body.strip():
            clair_bot.send_message(
                message.chat.id,
                "I need both a client number and a message before I can send anything to WhatsApp.",
            )
            return

        if _whatsapp_text(recipient, body.strip()):
            clair_bot.send_message(
                message.chat.id,
                f"✨ Sent from Renova WhatsApp to +{recipient}.",
            )
        else:
            clair_bot.send_message(
                message.chat.id,
                "I could not send that WhatsApp message. Please try once more; if it still fails, check that the client messaged Renova within the last 24 hours.",
            )


    @clair_bot.message_handler(commands=["wa"])
    def clair_whatsapp_command(message):
        if not is_clair_admin(message.from_user):
            return

        command_parts = (message.text or "").split(maxsplit=1)
        if len(command_parts) < 2:
            clair_bot.send_message(
                message.chat.id,
                "To reply to a client, either reply directly to their forwarded WhatsApp message, or use:\n/wa 614XXXXXXXX Your reply here",
            )
            return

        recipient = WHATSAPP_REPLY_TARGETS.get((message.chat.id, getattr(message.reply_to_message, "message_id", None)))
        if recipient:
            _send_clair_whatsapp_reply(message, recipient, command_parts[1])
            return

        recipient, separator, body = command_parts[1].partition(" ")
        _send_clair_whatsapp_reply(message, "".join(character for character in recipient if character.isdigit()), body if separator else "")


    @clair_bot.message_handler(func=lambda message: is_clair_admin(message.from_user) and bool(message.reply_to_message), content_types=["text"])
    def clair_whatsapp_direct_reply(message):
        recipient = WHATSAPP_REPLY_TARGETS.get((message.chat.id, message.reply_to_message.message_id))
        if not recipient:
            return
        _send_clair_whatsapp_reply(message, recipient, message.text or "")


    @clair_bot.message_handler(func=lambda message: True, content_types=["text"])
    def clair_text(message):
        text = message.text or ""
        admin = is_clair_admin(message.from_user)

        if admin and text == "📜 New Reading Requests":
            clair_bot.send_message(
                message.chat.id,
                "📜 **The listening room is waiting.**\n\nCustomer requests will appear here automatically when submitted.",
                reply_markup=admin_menu(),
                parse_mode="Markdown",
            )
            return
        if admin and text == "🕯 Reading Status":
            clair_bot.send_message(
                message.chat.id,
                "🕯 **The candle is steady.**\n\nNo unresolved requests are currently displayed here.",
                reply_markup=admin_menu(),
                parse_mode="Markdown",
            )
            return
        if admin and text == "🌙 Test Customer Flow":
            clair_bot.send_message(
                message.chat.id,
                "🌙 **Customer Flow Test**\n\nChoose the reading path:",
                reply_markup=customer_menu(),
                parse_mode="Markdown",
            )
            return
        if admin and text == "💬 Main Menu":
            clair_start(message)
            return

        if text == "🔮 3-Question Text Reading":
            SESSIONS[message.from_user.id] = {
                "stage": "questions",
                "questions": [],
                "service": "3-Question Text Reading",
            }
            clair_bot.send_message(message.chat.id, "Lovely. Please send your first question.")
            return
        if text == "🎙️ 15-Minute Voice Note":
            SESSIONS[message.from_user.id] = {"stage": "voice", "service": "15-Minute Voice Note Reading"}
            clair_bot.send_message(
                message.chat.id,
                "Wonderful. Send one main question, related thoughts, or say ‘general reading’. You may also send a Telegram voice message.",
            )
            return
        if text == "🌐 Renova Website":
            clair_bot.send_message(message.chat.id, WEBSITE_URL)
            return
        if text == "❓ Help":
            clair_bot.send_message(message.chat.id, "Choose a reading, answer Clair’s prompts, review your request, then tap Send to Jarrod.")
            return

        session = SESSIONS.get(message.from_user.id)
        if not session:
            return

        if session["stage"] == "questions":
            session["questions"].append(text)
            count = len(session["questions"])
            if count < 3:
                clair_bot.send_message(message.chat.id, f"Thank you — question {count} of 3 received.\n\nPlease send question {count + 1}.")
                return

            session["stage"] = "review"
            questions = session["questions"]
            menu = InlineKeyboardMarkup(row_width=1)
            menu.add(
                InlineKeyboardButton("✅ Send to Jarrod", callback_data="submit"),
                InlineKeyboardButton("🔄 Start Again", callback_data="restart"),
            )
            clair_bot.send_message(
                message.chat.id,
                f"🌙 Your questions are gathered.\n\n1. {questions[0]}\n\n2. {questions[1]}\n\n3. {questions[2]}\n\nSend these through to Jarrod?",
                reply_markup=menu,
            )
        elif session["stage"] == "voice":
            session["context"] = text
            session["stage"] = "review"
            menu = InlineKeyboardMarkup(row_width=1)
            menu.add(
                InlineKeyboardButton("✅ Send to Jarrod", callback_data="submit"),
                InlineKeyboardButton("🔄 Start Again", callback_data="restart"),
            )
            clair_bot.send_message(message.chat.id, "🌙 I’ve gathered your request. Send it through to Jarrod?", reply_markup=menu)


    @clair_bot.callback_query_handler(func=lambda call: True)
    def clair_callbacks(call):
        if call.data == "restart":
            SESSIONS.pop(call.from_user.id, None)
            clair_bot.answer_callback_query(call.id)
            clair_bot.send_message(call.message.chat.id, "The thread has been cleared. Choose a reading below.", reply_markup=customer_menu())
            return
        if call.data != "submit":
            return

        session = SESSIONS.get(call.from_user.id, {})
        user = call.from_user
        name = " ".join(filter(None, [user.first_name, user.last_name])) or "Unknown client"
        username = "@" + user.username if user.username else "No username"
        if session.get("service") == "3-Question Text Reading":
            content = "\n\n".join(f"Question {index}: {question}" for index, question in enumerate(session.get("questions", []), 1))
            heading = "🔮 NEW 3-QUESTION READING REQUEST"
        else:
            content = session.get("context", "General reading")
            heading = "🎙️ NEW VOICE NOTE READING REQUEST"

        admin_message = (
            f"{heading}\n\nClient: {name}\nUsername: {username}\nTelegram ID: {user.id}\n"
            f"Service: {session.get('service', 'Reading')}\n\n{content}"
        )
        clair_bot.send_message(CLAIR_ADMIN_ID, admin_message)
        clair_bot.answer_callback_query(call.id)
        clair_bot.send_message(
            call.message.chat.id,
            "Thank you — your request has been sent through to Jarrod. He’ll return to you during standard hours.",
            reply_markup=customer_menu(),
        )
        SESSIONS.pop(call.from_user.id, None)


    @clair_bot.message_handler(content_types=["voice"])
    def clair_voice(message):
        session = SESSIONS.get(message.from_user.id)
        if not session or session.get("stage") != "voice":
            return
        session["voice_file_id"] = message.voice.file_id
        session["stage"] = "review"
        menu = InlineKeyboardMarkup(row_width=1)
        menu.add(
            InlineKeyboardButton("✅ Send to Jarrod", callback_data="submit"),
            InlineKeyboardButton("🔄 Start Again", callback_data="restart"),
        )
        clair_bot.send_message(message.chat.id, "🌙 I’ve received your voice note. Send it through to Jarrod?", reply_markup=menu)


# ---------------------------------------------------------------------------
# WhatsApp Cloud API webhook + Renova customer flow
# ---------------------------------------------------------------------------
def _safe_compare(left, right):
    return hmac.compare_digest(left.encode("utf-8"), right.encode("utf-8"))


def _meta_post(payload):
    """Send a service-window WhatsApp message using the Cloud API."""
    if not WHATSAPP_ACCESS_TOKEN or not WHATSAPP_PHONE_NUMBER_ID:
        logger.warning("WhatsApp reply skipped: WHATSAPP_ACCESS_TOKEN is not configured")
        return False

    url = f"https://graph.facebook.com/{WHATSAPP_GRAPH_VERSION}/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            logger.info("WhatsApp reply accepted: %s", response.status)
            return 200 <= response.status < 300
    except urllib.error.HTTPError as error:
        logger.error("WhatsApp Graph API error %s: %s", error.code, error.read().decode("utf-8", "replace")[:800])
        return False
    except Exception:
        logger.exception("WhatsApp Graph API request failed")
        return False


def _whatsapp_text(to, body):
    return _meta_post(
        {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {"preview_url": True, "body": body},
        }
    )


def _whatsapp_message_summary(message):
    """Create a readable admin summary without copying untrusted markup into Telegram."""
    message_type = message.get("type", "message")
    if message_type == "text":
        return message.get("text", {}).get("body", "(empty text message)")
    if message_type == "interactive":
        interactive = message.get("interactive", {})
        reply = interactive.get("button_reply", {}) or interactive.get("list_reply", {})
        return f"Selected: {reply.get('title') or reply.get('id') or 'interactive option'}"
    if message_type == "image":
        caption = message.get("image", {}).get("caption", "")
        return f"Image received{': ' + caption if caption else ''}"
    if message_type == "document":
        document = message.get("document", {})
        filename = document.get("filename", "document")
        caption = document.get("caption", "")
        return f"Document received: {filename}{': ' + caption if caption else ''}"
    if message_type == "audio":
        return "Audio message received."
    if message_type == "video":
        caption = message.get("video", {}).get("caption", "")
        return f"Video received{': ' + caption if caption else ''}"
    if message_type == "sticker":
        return "Sticker received."
    if message_type == "location":
        location = message.get("location", {})
        return f"Location received: {location.get('latitude', '?')}, {location.get('longitude', '?')}"
    return f"{message_type.replace('_', ' ').title()} received."


def _forward_whatsapp_message_to_clair(sender, message, contacts):
    """Deliver client context to Jarrod's private Clair chat for human replies."""
    if not clair_bot:
        return

    profile_name = ""
    for contact in contacts:
        if contact.get("wa_id") == sender:
            profile_name = contact.get("profile", {}).get("name", "")
            break
    client_label = profile_name or "WhatsApp client"
    summary = _whatsapp_message_summary(message)
    admin_message = (
        "💬 WHATSAPP CLIENT MESSAGE\n\n"
        f"From: {client_label}\n"
        f"Number: +{sender}\n\n"
        f"{summary}\n\n"
        "Reply directly to this message to send from Renova WhatsApp. "
        "For an older message after a restart, use: /wa 614XXXXXXXX Your reply"
    )
    try:
        forwarded = clair_bot.send_message(CLAIR_ADMIN_ID, admin_message)
        WHATSAPP_REPLY_TARGETS[(CLAIR_ADMIN_ID, forwarded.message_id)] = sender
    except Exception:
        logger.exception("Could not forward WhatsApp client message to Clair admin chat")


def _whatsapp_main_menu(to):
    _meta_post(
        {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {
                    "text": "✨ Welcome to Renova Aether & Stone.\n\nI’m Renova — Jarrod’s first point of contact for grounded intuitive guidance, tarot, geographic energy and thoughtful reflection.\n\nHow may I guide you today?"
                },
                "action": {
                    "buttons": [
                        {"type": "reply", "reply": {"id": "renova_readings", "title": "Book a reading"}},
                        {"type": "reply", "reply": {"id": "renova_about", "title": "About Renova"}},
                        {"type": "reply", "reply": {"id": "renova_community", "title": "Community"}},
                    ]
                },
            },
        }
    )


def _whatsapp_reply(to, message):
    interactive = message.get("interactive", {})
    reply = interactive.get("button_reply", {}) or interactive.get("list_reply", {})
    key = (reply.get("id") or reply.get("title") or message.get("text", {}).get("body") or "").strip().lower()

    if key in {"renova_readings", "book a reading", "reading", "readings", "book", "text", "voice"}:
        _whatsapp_text(
            to,
            "🔮 Private readings with Jarrod\n\n"
            "• 3-Question Text Reading — $25 AUD\n"
            f"{TEXT_URL}\n\n"
            "• 15-Minute Voice Note Reading — $50 AUD\n"
            f"{VOICE_URL}\n\n"
            "After payment, send *paid* here with the reading type you selected. Jarrod will confirm the next step personally.",
        )
    elif key in {"renova_about", "about renova", "about"}:
        _whatsapp_text(
            to,
            "Renova Aether & Stone is a grounded space for intuitive and clairaudient listening, tarot analysis, geographic energy and thoughtful reflection. "
            "Jarrod combines spiritual insight with practical clarity and compassionate conversation.",
        )
    elif key in {"renova_community", "community", "telegram", "whatsapp"}:
        _whatsapp_text(
            to,
            "🌙 Join the Renova community:\n\n"
            f"Telegram Insights Group:\n{TELEGRAM_GROUP_URL}\n\n"
            f"WhatsApp Insights Community:\n{WHATSAPP_GROUP_URL}",
        )
    elif key in {"paid", "i paid", "payment sent"}:
        _whatsapp_text(
            to,
            "Thank you — your note is received. Please send a screenshot of the completed payment and say whether you selected the 3-question text reading or 15-minute voice note. Jarrod will confirm your reading path.",
        )
    else:
        _whatsapp_main_menu(to)


def _process_whatsapp_payload(payload):
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            if value.get("messaging_product") != "whatsapp":
                continue
            for message in value.get("messages", []):
                sender = message.get("from")
                if sender:
                    _forward_whatsapp_message_to_clair(sender, message, value.get("contacts", []))
                    _whatsapp_reply(sender, message)


class WhatsAppWebhookHandler(BaseHTTPRequestHandler):
    server_version = "RenovaWhatsAppWebhook/1.0"

    def _respond(self, status, body=b"", content_type="text/plain; charset=utf-8"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body:
            self.wfile.write(body)

    def log_message(self, fmt, *args):
        logger.info("Webhook %s - %s", self.address_string(), fmt % args)

    def do_GET(self):
        request_url = urlparse(self.path)
        if request_url.path == "/health":
            body = json.dumps(
                {
                    "ok": True,
                    "service": "renova-bots-whatsapp-webhook",
                    "phoneNumberConfigured": bool(WHATSAPP_PHONE_NUMBER_ID),
                    "tokenConfigured": bool(WHATSAPP_ACCESS_TOKEN),
                    "appSecretConfigured": bool(META_APP_SECRET),
                }
            ).encode("utf-8")
            self._respond(200, body, "application/json")
            return

        if request_url.path != "/api/whatsapp/webhook":
            self._respond(404, b"Not found")
            return

        query = parse_qs(request_url.query)
        mode = query.get("hub.mode", [""])[0]
        token = query.get("hub.verify_token", [""])[0]
        challenge = query.get("hub.challenge", [""])[0]
        if mode == "subscribe" and WHATSAPP_VERIFY_TOKEN and _safe_compare(token, WHATSAPP_VERIFY_TOKEN):
            self._respond(200, challenge.encode("utf-8"))
        else:
            self._respond(403, b"Forbidden")

    def do_POST(self):
        if urlparse(self.path).path != "/api/whatsapp/webhook":
            self._respond(404, b"Not found")
            return

        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        signature = self.headers.get("X-Hub-Signature-256", "")

        if not META_APP_SECRET:
            logger.error("Webhook rejected: META_APP_SECRET is not configured")
            self._respond(503, b"Webhook security is not configured")
            return

        expected = "sha256=" + hmac.new(META_APP_SECRET.encode("utf-8"), raw, hashlib.sha256).hexdigest()
        if not signature or not _safe_compare(signature, expected):
            logger.warning("Webhook rejected: invalid Meta signature")
            self._respond(403, b"Invalid signature")
            return

        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            self._respond(400, b"Invalid JSON")
            return

        # Acknowledge immediately; process outgoing response asynchronously.
        self._respond(200, b"EVENT_RECEIVED")
        threading.Thread(target=_process_whatsapp_payload, args=(payload,), daemon=True).start()


def start_whatsapp_webhook():
    port = int(os.getenv("PORT", "8080"))
    server = ThreadingHTTPServer(("0.0.0.0", port), WhatsAppWebhookHandler)
    logger.info("WhatsApp webhook server listening on port %s", port)
    server.serve_forever()


def start_telegram_bots():
    bots = [bot for bot in (renova_bot, nero_bot, clair_bot) if bot]
    threads = [threading.Thread(target=bot.infinity_polling, daemon=True) for bot in bots]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()


if __name__ == "__main__":
    threading.Thread(target=start_whatsapp_webhook, daemon=True).start()
    start_telegram_bots()
