import json

import frappe
from frappe import _

from tcb_customize.api.google_calendar import notify_event_attendees
from tcb_customize.services.whatsapp import send_template

VERIFY_TOKEN = "tcb_whatsapp_verify"


@frappe.whitelist()
def test_whatsapp():
    return send_template(
        phone="919728273069",
        template_name="hello_world"
    )


@frappe.whitelist()
def send_event_whatsapp(doc, method=None):
    return notify_event_attendees(doc, method)


@frappe.whitelist(allow_guest=True)
def webhook():
    request = frappe.request

    if request.method == "GET":
        mode = frappe.form_dict.get("hub.mode")
        token = frappe.form_dict.get("hub.verify_token")
        challenge = frappe.form_dict.get("hub.challenge")

    if mode == "subscribe":
        if token == VERIFY_TOKEN:
            return challenge
        return "Invalid Verify Token"

        return "Webhook is running" 

    elif request.method == "POST":
        data = json.loads(request.get_data(as_text=True))

        frappe.log_error(
            title="WhatsApp Incoming",
            message=frappe.as_json(data)
        )

        return "EVENT_RECEIVED"

    return "OK"