import json

import frappe
from frappe.utils import add_to_date, formatdate, get_datetime

from tcb_customize.api.google_calendar import notify_customer_meeting
from tcb_customize.services.email import reply_email
from tcb_customize.services.team_inbox import get_conversation, mark_as_read, save_message
from tcb_customize.services.whatsapp import send_text_message


@frappe.whitelist()
def get_threads():

    conversations = frappe.get_all(
        "Team Inbox Conversation",
        fields=[
            "name",
            "title",
            "phone",
            "email",
            "last_channel",
            "last_message",
            "last_message_time",
            "unread_count",
            "status",
        ],
        order_by="last_message_time desc",
    )

    threads = []

    for c in conversations:

        threads.append(
            {
                "name": c.name,
                "title": c.title,
                "contact": c.title,
                "channel": c.last_channel,
                "last_channel": c.last_channel,
                "last_message": c.last_message or "",
                "timestamp": c.last_message_time,
                "unread": c.unread_count or 0,
                "status": c.status,
            }
        )

    return threads


@frappe.whitelist()
def get_messages(conversation):

    messages = frappe.get_all(
        "Team Inbox Message",
        filters={
            "conversation": conversation,
        },
        fields=[
            "name",
            "direction",
            "channel",
            "sender",
            "receiver",
            "message",
            "status",
            "creation",
        ],
        order_by="creation asc",
    )

    for m in messages:

        m.creation = formatdate(
            m.creation,
            "dd-mm-yy",
        )

    return messages


@frappe.whitelist()
def search_threads(keyword):

    keyword = (keyword or "").strip()

    if not keyword:
        return get_threads()

    conversations = frappe.get_all(
        "Team Inbox Conversation",
        filters=[
            [
                "title",
                "like",
                f"%{keyword}%",
            ]
        ],
        fields=[
            "name",
            "title",
            "last_channel",
            "last_message",
            "last_message_time",
            "unread_count",
            "status",
        ],
        order_by="last_message_time desc",
    )

    result = []

    for c in conversations:

        result.append(
            {
                "name": c.name,
                "title": c.title,
                "contact": c.title,
                "channel": c.last_channel,
                "last_channel": c.last_channel,
                "last_message": c.last_message or "",
                "timestamp": c.last_message_time,
                "unread": c.unread_count or 0,
                "status": c.status,
            }
        )

    return result


@frappe.whitelist()
def send_reply(conversation, message):
    message = (message or "").strip()

    if not conversation:
        frappe.throw("Conversation is required.")

    if not message:
        frappe.throw("Reply message is required.")

    conv = get_conversation(conversation)
    channel = (conv.last_channel or "WhatsApp").strip().lower()

    if channel == "whatsapp":
        if not conv.phone:
            frappe.throw("This conversation has no WhatsApp number.")

        result = send_text_message(
            phone=conv.phone,
            message=message,
            party_type=conv.party_type,
            party=conv.party,
        )
    elif channel == "email":
        result = reply_email(conversation, message)
    else:
        frappe.throw(f"Unsupported channel: {conv.last_channel}")

    if result.get("ok"):
        mark_as_read(conversation)

    return result


@frappe.whitelist()
def get_employees():
    return frappe.get_all(
        "Employee",
        filters={"status": "Active"},
        fields=["name", "employee_name"],
        order_by="employee_name asc",
    )


@frappe.whitelist()
def schedule_meeting(conversation, subject, starts_on, duration=30, employees=None):
    subject = (subject or "").strip()
    if not conversation:
        frappe.throw("Conversation is required.")
    if not subject:
        frappe.throw("Meeting subject is required.")
    if not starts_on:
        frappe.throw("Meeting date and time are required.")

    conv = get_conversation(conversation)
    starts_on = get_datetime(starts_on)
    duration = int(duration or 30)
    ends_on = add_to_date(starts_on, minutes=duration)

    google_calendar = "Test"

    if isinstance(employees, str):
        employees = json.loads(employees or "[]")
    employees = employees or []

    participants = []

    customer_email = conv.email
    if conv.party_type == "Lead" and conv.party and not customer_email:
        customer_email = frappe.db.get_value("Lead", conv.party, "email_id")

    if conv.party_type and conv.party:
        participant = {
            "reference_doctype": conv.party_type,
            "reference_docname": conv.party,
        }
        if customer_email:
            participant["email"] = customer_email
        participants.append(participant)
    elif customer_email:
        participants.append({"email": customer_email})

    for employee in employees:
        participants.append(
            {
                "reference_doctype": "Employee",
                "reference_docname": employee,
            }
        )

    try:
        event = frappe.get_doc(
            {
                "doctype": "Event",
                "subject": subject,
                "event_category": "Meeting",
                "event_type": "Public",
                "starts_on": starts_on,
                "ends_on": ends_on,
                "sync_with_google_calendar": 1,
                "google_calendar": google_calendar,
                "add_video_conferencing": 1,
                "event_participants": participants,
                "reference_doctype": conv.party_type,
                "reference_docname": conv.party,
            }
        )
        event.insert()
        event.reload()
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Schedule Meeting: Event creation failed")
        return {
            "ok": False,
            "error": "Failed to create the meeting event. Check the Error Log for details.",
        }

    # Notifications run after the event is safely saved.
    # Failures here are logged but do NOT roll back the event.
    try:
        notify_customer_meeting(conv, event)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Schedule Meeting: notification failed")

    meeting_note = (
        f"Meeting scheduled: {subject} on {starts_on.strftime('%d %b %Y %I:%M %p')}"
    )
    if event.google_meet_link:
        meeting_note += f"\nJoin: {event.google_meet_link}"

    try:
        save_message(
            channel=conv.last_channel or "WhatsApp",
            direction="Outgoing",
            sender=frappe.session.user,
            receiver=conv.title,
            phone=conv.phone,
            email=conv.email,
            party_type=conv.party_type,
            party=conv.party,
            message=meeting_note,
            status="Sent",
            message_type="Meeting",
        )
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Schedule Meeting: save_message failed")

    return {
        "ok": True,
        "event": event.name,
        "google_meet_link": event.google_meet_link,
    }