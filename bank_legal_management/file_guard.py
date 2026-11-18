import frappe

SENSITIVE_ATTACHMENT_DOCTYPES = {
	"Legal Case",
	"Legal Hearing",
	"Legal Counsel",
	"Legal Contract",
	"Contract Obligation",
	"Legal Opinion Request",
	"Legal Opinion",
	"Employee Legal Grievance",
	"Grievance Action Log",
	"Employee Grievance Clarification",
	"Employee Complaints Committee",
	"Employee Complaints Committee Meeting",
	"Legal Correspondence",
	"Legal Document Register",
	"Legal Expense",
	"Legal Decision",
}


def keep_attachments_private(doc, method=None):
	if doc.attached_to_doctype in SENSITIVE_ATTACHMENT_DOCTYPES:
		doc.is_private = 1
		if not doc.folder:
			doc.folder = "Home/Attachments"


def prevent_attachment_move(doc, method=None):
	if doc.is_new():
		return
	old = doc.get_doc_before_save()
	if not old:
		return
	if old.attached_to_doctype in SENSITIVE_ATTACHMENT_DOCTYPES and (
		doc.attached_to_doctype != old.attached_to_doctype
		or doc.attached_to_name != old.attached_to_name
	):
		frappe.throw(
			frappe._("لا يمكن نقل مرفق مرتبط بسجل قانوني إلى سجل آخر."),
			frappe.PermissionError,
		)
