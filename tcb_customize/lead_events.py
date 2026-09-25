import frappe

from tcb_customize.services.whatsapp import send_template


def _lead_message(customer, enquiry):
    return (
        f"Hi {customer},\n\n"
        f"Thank you for contacting us regarding {enquiry}.\n\n"
        "Our team has received your enquiry and will connect with you shortly.\n\n"
        "Regards,\nTeam"
    )


def _lead_whatsapp_template():
    settings = frappe.get_single("WhatsApp Integration")
    return (
        settings.get("lead_greeting_template")
        or settings.get("lead_template_name")
        or settings.get("lead_template")
        or settings.get("template_name")
        or "lead_enquiry"
    )



def after_insert(doc, method=None):
    """Send a first greeting for every newly-created Lead and add it to Team Inbox."""
    phone = doc.get("whatsapp_no") or doc.get("mobile_no")
    email = doc.get("email_id")
    customer = doc.get("lead_name") or "Customer"
    enquiry = doc.get("source") or "our services"
    message = _lead_message(customer, enquiry)

    if phone:
        try:
            template_name = _lead_whatsapp_template()
            parameters = [] if template_name == "hello_world" else [customer, enquiry]
            whatsapp_message = "Hello World" if template_name == "hello_world" else message
            send_template(
                phone=phone,
                template_name=template_name,
                parameters=parameters,
                party_type="Lead",
                party=doc.name,
                message_text=whatsapp_message,
            )
        except Exception:
            frappe.log_error(frappe.get_traceback(), "Lead WhatsApp Error")

    if email:
        try:
            from tcb_customize.services.email import send_email
            send_email(
                to=email,
                subject="Thank you for contacting us",
                message=message,
                party_type="Lead",
                party=doc.name,
            )
        except Exception:
            frappe.log_error(frappe.get_traceback(), "Lead Email Error")


def on_trash(doc, method=None):
    """Delete linked Team Inbox Messages, Conversations and Event references before the Lead is removed."""
    lead = doc.name

    # 1. Unlink Lead from any Events (don't delete the event, just clear the reference)
    for event_name in frappe.get_all(
        "Event",
        filters={"reference_doctype": "Lead", "reference_docname": lead},
        pluck="name",
    ):
        frappe.db.set_value(
            "Event",
            event_name,
            {"reference_doctype": "", "reference_docname": ""},
            update_modified=False,
        )

    # 2. Remove Lead from Event Participants child table
    frappe.db.delete("Event Participants", {
        "reference_doctype": "Lead",
        "reference_docname": lead,
    })

    # 3. Delete Team Inbox Messages then Conversations
    conversations = frappe.get_all(
        "Team Inbox Conversation",
        filters={"party_type": "Lead", "party": lead},
        pluck="name",
    )
    for conv in conversations:
        for msg in frappe.get_all(
            "Team Inbox Message",
            filters={"conversation": conv},
            pluck="name",
        ):
            frappe.delete_doc("Team Inbox Message", msg, ignore_permissions=True, force=True)
        frappe.delete_doc("Team Inbox Conversation", conv, ignore_permissions=True, force=True)
