import json

import frappe
from frappe import _

from tcb_customize.services.team_inbox import find_party_by_phone, save_message

VERIFY_TOKEN = "tcb_whatsapp_verify"


def _extract_messages(data):
    messages = []

    for entry in data.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            for message in value.get("messages", []):
                messages.append(message)

    return messages


def _message_text(message):
    message_type = message.get("type")

    if message_type == "text":
        return (message.get("text") or {}).get("body")

    if message_type == "button":
        return (message.get("button") or {}).get("text")

    if message_type == "interactive":
        interactive = message.get("interactive") or {}
        if interactive.get("type") == "button_reply":
            return (interactive.get("button_reply") or {}).get("title")
        if interactive.get("type") == "list_reply":
            return (interactive.get("list_reply") or {}).get("title")

    return f"[{message_type or 'unsupported'} message]"


def _save_incoming_message(message):
    phone = message.get("from")
    text = _message_text(message)
    external_id = message.get("id")

    if not phone or not text:
        return

    if external_id and frappe.db.exists(
        "Team Inbox Message",
        {"external_message_id": external_id},
    ):
        return

    party_type, party = find_party_by_phone(phone)
    settings = frappe.get_single("WhatsApp Integration")

    save_message(
        channel="WhatsApp",
        direction="Incoming",
        sender=phone,
        receiver=settings.get("phone_number_id") if settings else None,
        phone=phone,
        party_type=party_type,
        party=party,
        message=text,
        status="Received",
        message_type="Text",
        external_message_id=external_id,
    )


@frappe.whitelist(allow_guest=True)
def webhook():
    """
    Meta WhatsApp Webhook
    GET  -> Webhook verification
    POST -> Incoming WhatsApp messages
    """
    request = frappe.request

    if request.method == "GET":
        mode = frappe.form_dict.get("hub.mode")
        token = frappe.form_dict.get("hub.verify_token")
        challenge = frappe.form_dict.get("hub.challenge")

        if mode == "subscribe" and token == VERIFY_TOKEN:
            return challenge

        frappe.throw(_("Verification failed"))

    if request.method == "POST":
        data = json.loads(request.get_data(as_text=True))

        try:
            for message in _extract_messages(data):
                _save_incoming_message(message)
        except Exception:
            frappe.log_error(frappe.get_traceback(), "WhatsApp Webhook Error")

        return "EVENT_RECEIVED"

    return "OK"
