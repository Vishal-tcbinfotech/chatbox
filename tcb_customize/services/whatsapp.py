import re

import frappe
import requests
from frappe.utils import escape_html

from tcb_customize.services.team_inbox import save_message


def _normalize_phone(phone):
    phone = re.sub(r"\D", "", phone or "")
    return f"91{phone}" if len(phone) == 10 else phone


def _display_message(parameters, message_text=None):
    if message_text:
        return message_text

    customer = parameters[0] if parameters else "Customer"
    enquiry = parameters[1] if parameters and len(parameters) > 1 else "our services"
    return (
        f"Hi {customer},\n\n"
        f"Thank you for contacting us regarding {enquiry}.\n\n"
        "Our team will connect with you shortly."
    )


def _record_message(
    phone,
    settings,
    party_type,
    party,
    message,
    status,
    error=None,
    external_id=None,
    message_type="Template",
):
    return save_message(
        channel="WhatsApp",
        direction="Outgoing",
        sender=settings.get("phone_number_id") if settings else None,
        receiver=phone,
        phone=phone,
        party_type=party_type,
        party=party,
        message=message,
        status=status,
        message_type=message_type,
        error_message=error,
        external_message_id=external_id,
    )


def _store_communication(phone, subject, message, response):
    try:
        message_id = (response.get("messages") or [{}])[0].get("id")
        frappe.get_doc(
            {
                "doctype": "Communication",
                "communication_type": "Communication",
                "communication_medium": "Chat",
                "sent_or_received": "Sent",
                "status": "Open",
                "subject": f"WhatsApp: {subject}",
                "content": escape_html(message).replace("\n", "<br>"),
                "phone_no": phone,
                "message_id": message_id,
                "delivery_status": "Sent",
            }
        ).insert(ignore_permissions=True)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Communication Log Error")


def send_template(phone, template_name, parameters=None, party_type=None, party=None, message_text=None):
    """Send a Meta-approved WhatsApp template and always record its result in Team Inbox."""
    parameters = parameters or []
    display_message = _display_message(parameters, message_text)
    phone = _normalize_phone(phone)

    if not phone:
        frappe.log_error("Lead has no valid WhatsApp/mobile number.", "Lead WhatsApp Error")
        return {"ok": False, "error": "A valid WhatsApp/mobile number is required."}

    settings = frappe.get_single("WhatsApp Integration")
    enabled = settings.get("enabled")
    phone_number_id = settings.get("phone_number_id")
    try:
        token = settings.get_password("access_token")
    except Exception:
        token = None

    if not enabled or not phone_number_id or not token:
        error = "WhatsApp Integration must be enabled and have Phone Number ID and Access Token configured."
        _record_message(phone, settings, party_type, party, display_message, "Failed", error)
        frappe.log_error(error, "Lead WhatsApp Configuration Error")
        return {"ok": False, "error": error}

    if not template_name:
        error = "Configure a Lead WhatsApp template name before creating a Lead."
        _record_message(phone, settings, party_type, party, display_message, "Failed", error)
        frappe.log_error(error, "Lead WhatsApp Configuration Error")
        return {"ok": False, "error": error}

    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": settings.get("template_language") or "en_US"},
        },
    }
    if parameters:
        payload["template"]["components"] = [{
            "type": "body",
            "parameters": [{"type": "text", "text": str(value)} for value in parameters],
        }]

    try:
        response = requests.post(
            f"https://graph.facebook.com/v25.0/{phone_number_id}/messages",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=payload,
            timeout=30,
        )
        try:
            data = response.json()
        except ValueError:
            data = {"error": response.text or f"HTTP {response.status_code}"}
    except requests.RequestException:
        error = frappe.get_traceback()
        _record_message(phone, settings, party_type, party, display_message, "Failed", error)
        frappe.log_error(error, "Lead WhatsApp Delivery Error")
        return {"ok": False, "error": "WhatsApp request failed. See Error Log."}

    if response.status_code >= 400:
        error = data.get("error", {}).get("message") if isinstance(data.get("error"), dict) else response.text
        _record_message(phone, settings, party_type, party, display_message, "Failed", error)
        frappe.log_error(frappe.as_json(data), "Lead WhatsApp Delivery Error")
        return {"ok": False, "error": error or "WhatsApp rejected the template."}

    external_id = (data.get("messages") or [{}])[0].get("id")
    _store_communication(phone, template_name, display_message, data)
    _record_message(phone, settings, party_type, party, display_message, "Sent", external_id=external_id)
    return {"ok": True, "message_id": external_id, "response": data}


def send_text_message(phone, message, party_type=None, party=None):
    """Send a plain WhatsApp text message and record it in Team Inbox."""
    phone = _normalize_phone(phone)
    message = (message or "").strip()

    if not phone:
        return {"ok": False, "error": "A valid WhatsApp/mobile number is required."}

    if not message:
        return {"ok": False, "error": "Message text is required."}

    settings = frappe.get_single("WhatsApp Integration")
    enabled = settings.get("enabled")
    phone_number_id = settings.get("phone_number_id")
    try:
        token = settings.get_password("access_token")
    except Exception:
        token = None

    if not enabled or not phone_number_id or not token:
        error = "WhatsApp Integration must be enabled and have Phone Number ID and Access Token configured."
        _record_message(phone, settings, party_type, party, message, "Failed", error, message_type="Text")
        frappe.log_error(error, "WhatsApp Configuration Error")
        return {"ok": False, "error": error}

    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "text",
        "text": {"body": message},
    }

    try:
        response = requests.post(
            f"https://graph.facebook.com/v25.0/{phone_number_id}/messages",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=payload,
            timeout=30,
        )
        try:
            data = response.json()
        except ValueError:
            data = {"error": response.text or f"HTTP {response.status_code}"}
    except requests.RequestException:
        error = frappe.get_traceback()
        _record_message(phone, settings, party_type, party, message, "Failed", error, message_type="Text")
        frappe.log_error(error, "WhatsApp Delivery Error")
        return {"ok": False, "error": "WhatsApp request failed. See Error Log."}

    if response.status_code >= 400:
        error = data.get("error", {}).get("message") if isinstance(data.get("error"), dict) else response.text
        _record_message(phone, settings, party_type, party, message, "Failed", error, message_type="Text")
        frappe.log_error(frappe.as_json(data), "WhatsApp Delivery Error")
        return {"ok": False, "error": error or "WhatsApp rejected the message."}

    external_id = (data.get("messages") or [{}])[0].get("id")
    _store_communication(phone, "Text Message", message, data)
    _record_message(
        phone,
        settings,
        party_type,
        party,
        message,
        "Sent",
        external_id=external_id,
        message_type="Text",
    )
    return {"ok": True, "message_id": external_id, "response": data}
