import frappe


@frappe.whitelist()
def get_conversations():
    return frappe.get_all(
        "Team Inbox Conversation",
        fields=[
            "name",
            "title",
            "phone",
            "email",
            "last_message",
            "last_message_time",
            "last_channel",
            "unread_count",
        ],
        order_by="last_message_time desc",
    )

@frappe.whitelist()
def get_messages(conversation):

    return frappe.get_all(
        "Team Inbox Message",
        filters={
            "conversation": conversation
        },
        fields=[
            "name",
            "direction",
            "channel",
            "sender",
            "receiver",
            "message",
            "creation",
            "status",
        ],
        order_by="creation asc",
    )