app_name = "tcb_customize"
app_title = "tcb"
app_publisher = "yes"
app_description = "tcb custom changes"
app_email = "tcb@gmail.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "tcb_customize",
# 		"logo": "/assets/tcb_customize/logo.png",
# 		"title": "tcb",
# 		"route": "/tcb_customize",
# 		"has_permission": "tcb_customize.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/tcb_customize/css/tcb_customize.css"
# app_include_js = "/assets/tcb_customize/js/tcb_customize.js"

# include js, css files in header of web template
# web_include_css = "/assets/tcb_customize/css/tcb_customize.css"
# web_include_js = "/assets/tcb_customize/js/tcb_customize.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "tcb_customize/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "tcb_customize/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "tcb_customize.utils.jinja_methods",
# 	"filters": "tcb_customize.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "tcb_customize.install.before_install"
# after_install = "tcb_customize.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "tcb_customize.uninstall.before_uninstall"
# after_uninstall = "tcb_customize.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "tcb_customize.utils.before_app_install"
# after_app_install = "tcb_customize.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "tcb_customize.utils.before_app_uninstall"
# after_app_uninstall = "tcb_customize.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "tcb_customize.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
    "Event": {
        "before_insert": "tcb_customize.api.google_calendar.populate_employee_participant_emails",
        "before_save": "tcb_customize.api.google_calendar.populate_employee_participant_emails",
        "after_insert": "tcb_customize.api.google_calendar.notify_event_attendees",
        "on_update": "tcb_customize.api.google_calendar.notify_event_attendees",
    },
    "Lead": {
        "after_insert": "tcb_customize.lead_events.after_insert",
        "on_trash": "tcb_customize.lead_events.on_trash",
    },
    "Communication": {
        "after_insert": "tcb_customize.services.email.handle_incoming_communication",
    },
}
