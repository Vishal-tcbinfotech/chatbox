import frappe
from frappe.utils import now_datetime


def _normalize_channel(channel):
    return (channel or "WhatsApp").strip()


def _conversation_title(party_type=None, party=None, phone=None, email=None, channel=None):
    channel = _normalize_channel(channel)

    if party_type == "Lead" and party:
        lead_name = frappe.db.get_value("Lead", party, "lead_name")
        if lead_name:
            return f"{lead_name} ({channel})"

    if phone:
        return f"{phone} ({channel})"

    if email:
        return f"{email} ({channel})"

    return f"Unknown ({channel})"


def get_or_create_conversation(
    party_type=None,
    party=None,
    phone=None,
    email=None,
    channel="WhatsApp",
):
    """
    Returns an existing conversation for the same
    Lead + Channel OR Phone + Channel OR Email + Channel.

    Otherwise creates a new conversation.
    """

    channel = _normalize_channel(channel)

    conversation_name = None

    # --------------------------------------------------
    # 1. Find using Party
    # --------------------------------------------------

    if party_type and party:
        conversation_name = frappe.db.get_value(
            "Team Inbox Conversation",
            {
                "party_type": party_type,
                "party": party,
                "last_channel": channel,
            },
        )

    # --------------------------------------------------
    # 2. Find using Phone
    # --------------------------------------------------

    if not conversation_name and phone:
        conversation_name = frappe.db.get_value(
            "Team Inbox Conversation",
            {
                "phone": phone,
                "last_channel": channel,
            },
        )

    # --------------------------------------------------
    # 3. Find using Email
    # --------------------------------------------------

    if not conversation_name and email:
        conversation_name = frappe.db.get_value(
            "Team Inbox Conversation",
            {
                "email": email,
                "last_channel": channel,
            },
        )

    if conversation_name:
        return frappe.get_doc(
            "Team Inbox Conversation",
            conversation_name,
        )

    # --------------------------------------------------
    # Create Conversation
    # --------------------------------------------------

    conversation = frappe.get_doc(
        {
            "doctype": "Team Inbox Conversation",
            "title": _conversation_title(
                party_type=party_type,
                party=party,
                phone=phone,
                email=email,
                channel=channel,
            ),
            "party_type": party_type,
            "party": party,
            "phone": phone,
            "email": email,
            "status": "Open",
            "last_channel": channel,
            "last_message": "",
            "unread_count": 0,
            "last_message_time": now_datetime(),
        }
    )

    conversation.insert(ignore_permissions=True)

    return conversation


def update_conversation(
    conversation,
    message,
    channel,
    direction,
):
    """
    Update last message, timestamp and unread count.
    Never change last_channel — a conversation's channel is fixed at creation.
    """

    conversation.last_message = (message or "")[:300]
    conversation.last_message_time = now_datetime()

    if direction == "Incoming":
        conversation.unread_count = (conversation.unread_count or 0) + 1

    conversation.save(ignore_permissions=True)


def save_message(
    channel,
    direction,
    message,
    sender=None,
    receiver=None,
    party_type=None,
    party=None,
    phone=None,
    email=None,
    attachment=None,
    external_message_id=None,
    status="Sent",
    message_type="Text",
    error_message=None,
):
    """
    Creates/gets conversation
    Saves message
    Updates conversation
    """

    conversation = get_or_create_conversation(
        party_type=party_type,
        party=party,
        phone=phone,
        email=email,
        channel=channel,
    )

    inbox_message = frappe.get_doc(
        {
            "doctype": "Team Inbox Message",
            "conversation": conversation.name,
            "channel": _normalize_channel(channel),
            "direction": direction,
            "sender": sender,
            "receiver": receiver,
            "message": message,
            "attachment": attachment,
            "status": status,
            "external_message_id": external_message_id,
            "message_type": message_type,
            "created_at": now_datetime(),
            "error_message": error_message,
            "is_read": 0 if direction == "Incoming" else 1,
        }
    )

    inbox_message.insert(ignore_permissions=True)

    update_conversation(
        conversation=conversation,
        message=message,
        channel=channel,
        direction=direction,
    )

    if direction == "Incoming":
        notify_team_inbox_update(conversation.name)

    return inbox_message


def notify_team_inbox_update(conversation_name):
    frappe.publish_realtime(
        event="team_inbox_update",
        message={"conversation": conversation_name},
        after_commit=True,
    )


def mark_as_read(conversation_name):
    """
    Mark all incoming messages as read.
    """

    frappe.db.set_value(
        "Team Inbox Conversation",
        conversation_name,
        "unread_count",
        0,
        update_modified=False,
    )

    for name in frappe.get_all(
        "Team Inbox Message",
        filters={
            "conversation": conversation_name,
            "is_read": 0,
        },
        pluck="name",
    ):
        frappe.db.set_value(
            "Team Inbox Message",
            name,
            "is_read",
            1,
            update_modified=False,
        )

    frappe.db.commit()


def get_conversation(name):
    return frappe.get_doc(
        "Team Inbox Conversation",
        name,
    )


def find_party_by_phone(phone):
    import re

    normalized = re.sub(r"\D", "", phone or "")
    variants = {phone, normalized}

    if len(normalized) == 12 and normalized.startswith("91"):
        variants.add(normalized[2:])

    for variant in variants:
        if not variant:
            continue

        lead = frappe.db.get_value("Lead", {"whatsapp_no": variant}, "name")
        if lead:
            return "Lead", lead

        lead = frappe.db.get_value("Lead", {"mobile_no": variant}, "name")
        if lead:
            return "Lead", lead

    return None, None