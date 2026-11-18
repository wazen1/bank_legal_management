app_name = "bank_legal_management"
app_title = "نظام إدارة الشؤون القانونية"
app_publisher = "Libyan Bank"
app_description = "نظام متكامل لإدارة الشؤون القانونية: القضايا، الجلسات، العقود، الآراء، الشكاوى، اللجان، المراسلات والمستندات والمصروفات."
app_email = ""
app_license = "mit"

required_apps = ["frappe/erpnext"]

after_install = "bank_legal_management.setup.after_install"
after_migrate = "bank_legal_management.setup.after_migrate"

permission_query_conditions = {
	"Employee Legal Grievance": "bank_legal_management.permissions.employee_grievance_query",
	"Grievance Action Log": "bank_legal_management.permissions.grievance_action_log_query",
	"Legal Opinion Request": "bank_legal_management.permissions.legal_opinion_request_query",
	"Legal Opinion": "bank_legal_management.permissions.legal_opinion_query",
	"Legal Correspondence": "bank_legal_management.permissions.legal_correspondence_query",
	"Legal Document Register": "bank_legal_management.permissions.legal_document_query",
	"Legal Expense": "bank_legal_management.permissions.legal_expense_query",
}

has_permission = {
	"Employee Legal Grievance": "bank_legal_management.permissions.grievance_has_permission",
	"Grievance Action Log": "bank_legal_management.permissions.grievance_action_log_has_permission",
	"Legal Opinion Request": "bank_legal_management.permissions.legal_opinion_request_has_permission",
	"Legal Opinion": "bank_legal_management.permissions.legal_opinion_has_permission",
	"Legal Correspondence": "bank_legal_management.permissions.legal_correspondence_has_permission",
	"Legal Document Register": "bank_legal_management.permissions.legal_document_has_permission",
	"Legal Expense": "bank_legal_management.permissions.legal_expense_has_permission",
}

scheduler_events = {
	"daily": ["bank_legal_management.tasks.process_legal_deadlines"],
}

doc_events = {
	"File": {
		"before_insert": "bank_legal_management.file_guard.keep_attachments_private",
		"validate": "bank_legal_management.file_guard.keep_attachments_private",
		"on_update": "bank_legal_management.file_guard.prevent_attachment_move",
	},
}

doctype_js = {
	"Employee Legal Grievance": "public/js/employee_grievance.js",
	"Legal Case": "public/js/legal_case.js",
	"Legal Contract": "public/js/legal_contract.js",
	"Legal Opinion Request": "public/js/legal_opinion_request.js",
	"Employee Complaints Committee Meeting": "public/js/committee_meeting.js",
	"Legal Expense": "public/js/legal_expense.js",
	"Legal Decision": "public/js/legal_decision.js",
}

add_to_apps_screen = [
	{
		"name": "bank_legal_management",
		"logo": "/assets/bank_legal_management/images/legal.svg",
		"title": "نظام إدارة الشؤون القانونية",
		"route": "/app/legal-management",
	}
]
