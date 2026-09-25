import frappe

from frappe.integrations.doctype.google_calendar.google_calendar import (
    get_google_calendar_object,
)
from tcb_customize.services.whatsapp import send_template


def _get_participant_email(participant):
    """Return the attendee email, including Employee email fallbacks."""
    if participant.email:
        return participant.email

    if participant.reference_doctype != "Employee" or not participant.reference_docname:
        return None

    employee = frappe.get_cached_doc("Employee", participant.reference_docname)
    return employee.company_email or employee.personal_email or employee.user_id


def populate_employee_participant_emails(doc, method=None):
    """Store an Employee attendee email before Frappe syncs the Event to Google."""
    for participant in doc.event_participants:
        if not participant.email:
            participant.email = _get_participant_email(participant)


@frappe.whitelist()
def sync_google_calendar_attendees(event_name):
    """Manually refresh a synced Google event's attendee list."""
    event = frappe.get_doc("Event", event_name)

    if not event.sync_with_google_calendar or not event.google_calendar:
        frappe.throw("This Event is not linked with Google Calendar.")

    if not event.google_calendar_event_id:
        frappe.throw("This Event has not yet been created in Google Calendar.")

    attendees = [
        {"email": email}
        for participant in event.event_participants
        if (email := _get_participant_email(participant))
    ]

    service, google_calendar = get_google_calendar_object(event.google_calendar)
    google_event = (
        service.events()
        .get(
            calendarId=google_calendar.google_calendar_id,
            eventId=event.google_calendar_event_id,
        )
        .execute()
    )
    google_event["attendees"] = attendees

    updated_event = (
        service.events()
        .update(
            calendarId=google_calendar.google_calendar_id,
            eventId=event.google_calendar_event_id,
            body=google_event,
            sendUpdates="all",
        )
        .execute()
    )

    return {
        "status": "success",
        "updated_event_id": updated_event["id"],
        "attendees": attendees,
    }


def _meeting_details(event):
    details = " ".join((event.location or "-").split())
    if event.google_meet_link:
        details = f"{details} | Join Google Meet: {event.google_meet_link}"
    return details


def notify_customer_meeting(conversation, event):
    """Notify the customer about a scheduled meeting via WhatsApp and email."""
    settings = frappe.get_single("WhatsApp Integration")

    # Use dedicated meeting template field, fall back to meeting_invitation
    meeting_template = (
        settings.get("meeting_template_name")
        or "meeting_invitation"
    )

    if conversation.phone and settings.enabled:
        customer_name = conversation.title or "Customer"
        if conversation.party_type == "Lead" and conversation.party:
            customer_name = (
                frappe.db.get_value("Lead", conversation.party, "lead_name")
                or customer_name
            )

        parameters = [
            customer_name,
            event.subject,
            event.starts_on.strftime("%d %b %Y"),
            event.starts_on.strftime("%I:%M %p"),
            event.google_meet_link or "-",
        ]

        try:
            send_template(
                phone=conversation.phone,
                template_name=meeting_template,
                parameters=parameters,
                party_type=conversation.party_type,
                party=conversation.party,
            )
        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                "Team Inbox meeting WhatsApp notification error",
            )

    customer_email = conversation.email
    if conversation.party_type == "Lead" and conversation.party and not customer_email:
        customer_email = frappe.db.get_value("Lead", conversation.party, "email_id")

    if customer_email:
        from tcb_customize.services.email import send_email

        body = (
            f"Your meeting '{event.subject}' is scheduled for "
            f"{event.starts_on.strftime('%d %b %Y at %I:%M %p')}."
        )
        if event.google_meet_link:
            body += f"\n\nJoin Google Meet: {event.google_meet_link}"

        try:
            send_email(
                to=customer_email,
                subject=f"Meeting: {event.subject}",
                message=body,
                party_type=conversation.party_type,
                party=conversation.party,
            )
        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                "Team Inbox meeting email notification error",
            )


def notify_event_attendees(doc, method=None):
    """Send the approved WhatsApp meeting template after Google Calendar has synced."""
    if not doc.sync_with_google_calendar or doc.flags.tcb_whatsapp_notified:
        return

    doc.flags.tcb_whatsapp_notified = True
    event = frappe.get_doc("Event", doc.name)
    if not event.google_calendar_event_id:
        return

    previous_event = doc.get_doc_before_save()
    previous_employee_participants = set()
    if previous_event:
        previous_employee_participants = {
            participant.reference_docname
            for participant in previous_event.event_participants
            if participant.reference_doctype == "Employee" and participant.reference_docname
        }

    settings = frappe.get_single("WhatsApp Integration")
    if not settings.enabled or not settings.template_name:
        return

    for participant in event.event_participants:
        if participant.reference_doctype != "Employee" or not participant.reference_docname:
            continue
        if participant.reference_docname in previous_employee_participants:
            continue

        employee = frappe.get_cached_doc("Employee", participant.reference_docname)
        if not employee.cell_number:
            continue

        try:
            print("Sending WhatsApp to", employee.cell_number)
            parameters = [
                employee.employee_name,
                event.subject,
                event.starts_on.strftime("%d %b %Y"),
                event.starts_on.strftime("%I:%M %p"),
                _meeting_details(event),
            ]
            if settings.template_name == "hello_world":
                parameters = None

            send_template(
                phone=employee.cell_number,
                template_name=settings.template_name,
                parameters=parameters,
            )
        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                f"Event WhatsApp notification error for {employee.name}",
            )
