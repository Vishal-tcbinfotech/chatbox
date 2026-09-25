import frappe
from frappe.utils import escape_html, strip_html

from tcb_customize.services.team_inbox import get_conversation, save_message

EMAIL_ACCOUNT = "TCB Infotech"


def _get_email_account():
    if not frappe.db.exists("Email Account", EMAIL_ACCOUNT):
        frappe.log_error(
            f"Email Account '{EMAIL_ACCOUNT}' not found. Configure it at Tools > Email Account.",
            "Team Inbox Email Account Missing",
        )
        return None
    return frappe.get_doc("Email Account", EMAIL_ACCOUNT)


def log_email(
    direction,
    sender,
    receiver,
    email,
    message,
    party_type=None,
    party=None,
    status="Sent",
    error_message=None,
    external_message_id=None,
):
    return save_message(
        channel="Email",
        direction=direction,
        sender=sender,
        receiver=receiver,
        email=email,
        party_type=party_type,
        party=party,
        message=message,
        status=status,
        message_type="Email",
        error_message=error_message,
        external_message_id=external_message_id,
    )


def _last_incoming_subject(email, party_type=None, party=None):
    filters = {
        "communication_medium": "Email",
        "sent_or_received": "Received",
    }

    if party_type and party:
        filters["reference_doctype"] = party_type
        filters["reference_name"] = party
    else:
        filters["sender"] = email

    rows = frappe.get_all(
        "Communication",
        filters=filters,
        fields=["subject"],
        order_by="creation desc",
        limit=1,
    )

    if rows and rows[0].subject:
        return rows[0].subject

    return "Your enquiry"


def send_email(to, subject, message, party_type=None, party=None):
    message = (message or "").strip()

    if not to:
        return {"ok": False, "error": "Recipient email is required."}

    if not message:
        return {"ok": False, "error": "Message text is required."}

    account = _get_email_account()
    if not account:
        return {"ok": False, "error": f"Email Account '{EMAIL_ACCOUNT}' not found. Configure it at Tools > Email Account."}
    subject = (subject or "Message from TCB").strip()
    content = "<br>".join(escape_html(message).split("\n"))

    try:
        frappe.sendmail(
            recipients=[to],
            subject=subject,
            message=content,
            sender=account.email_id,
            reply_to=account.email_id,
            reference_doctype=party_type,
            reference_name=party,
            delayed=False,
        )
    except Exception:
        error = frappe.get_traceback()
        log_email(
            "Outgoing",
            account.email_id,
            to,
            to,
            message,
            party_type,
            party,
            "Failed",
            error,
        )
        frappe.log_error(error, "Team Inbox Email Error")
        return {"ok": False, "error": "Email could not be sent. See Error Log."}

    log_email(
        "Outgoing",
        account.email_id,
        to,
        to,
        message,
        party_type,
        party,
        "Sent",
    )
    return {"ok": True}


def reply_email(conversation, message):
    conv = get_conversation(conversation)
    email = conv.email

    if not email and conv.party_type == "Lead" and conv.party:
        email = frappe.db.get_value("Lead", conv.party, "email_id")

    if not email:
        return {"ok": False, "error": "This conversation has no email address."}

    subject = _last_incoming_subject(email, conv.party_type, conv.party)
    if not subject.lower().startswith("re:"):
        subject = f"Re: {subject}"

    return send_email(
        to=email,
        subject=subject,
        message=message,
        party_type=conv.party_type,
        party=conv.party,
    )


def handle_incoming_communication(doc, method=None):
    """Save incoming ERPNext emails into Team Inbox."""
    if doc.doctype != "Communication":
        return

    if doc.sent_or_received != "Received":
        return

    if doc.communication_medium != "Email":
        return

    if not frappe.db.exists("Email Account", EMAIL_ACCOUNT):
        return

    # doc.email_account stores the Email Account name (e.g. "TCB Infotech"),
    # not the email address. Fetch the name for our account and compare.
    our_account_name = frappe.db.get_value("Email Account", EMAIL_ACCOUNT, "name")
    if doc.email_account and our_account_name and doc.email_account != our_account_name:
        return

    if doc.name and frappe.db.exists(
        "Team Inbox Message",
        {"external_message_id": doc.name},
    ):
        return

    customer_email = doc.sender
    if not customer_email:
        return

    account = _get_email_account()
    if customer_email.lower() == account.email_id.lower():
        return

    message_text = strip_html(doc.content or "") or doc.subject or "(No content)"
    party_type = doc.reference_doctype
    party = doc.reference_name

    if not party:
        lead = frappe.db.get_value("Lead", {"email_id": customer_email}, "name")
        if lead:
            party_type = "Lead"
            party = lead

    save_message(
        channel="Email",
        direction="Incoming",
        sender=customer_email,
        receiver=account.email_id,
        email=customer_email,
        party_type=party_type,
        party=party,
        message=message_text,
        status="Received",
        message_type="Email",
        external_message_id=doc.name,
    )
