import frappe
from frappe import _
from frappe.utils import add_days, getdate, today


SOURCES = (
	("Legal Hearing", "جلسة", "hearing_date", "legal_case"),
	("Legal Contract", "انتهاء عقد", "end_date", "contract_title"),
	("Contract Obligation", "التزام تعاقدي", None, "description"),
	("Legal Opinion Request", "طلب رأي", "due_date", "request_title"),
	("Employee Complaints Committee Meeting", "اجتماع لجنة", "meeting_date", "name"),
	("Legal Correspondence", "متابعة مراسلة", "due_date", "subject"),
	("Legal Document Register", "انتهاء مستند", "expiry_date", "document_title"),
)


def execute(filters=None):
	filters = frappe._dict(filters or {})
	from_date = filters.get("from_date") or today()
	to_date = filters.get("to_date") or add_days(today(), 60)
	deadline_type = filters.get("deadline_type")
	columns = [
		{"label": _("النوع"), "fieldname": "deadline_type", "fieldtype": "Data", "width": 120},
		{"label": _("المرجع"), "fieldname": "reference", "fieldtype": "Dynamic Link", "options": "reference_doctype", "width": 150},
		{"label": _("العنوان"), "fieldname": "title", "fieldtype": "Data", "width": 220},
		{"label": _("التاريخ"), "fieldname": "deadline_date", "fieldtype": "Date", "width": 110},
		{"label": _("الحالة"), "fieldname": "status", "fieldtype": "Data", "width": 120},
		{"label": _("المسؤول"), "fieldname": "owner", "fieldtype": "Link", "options": "User", "width": 150},
	]
	data = []
	for doctype, label, date_field, title_field in SOURCES:
		if deadline_type and deadline_type != label:
			continue
		if not frappe.has_permission(doctype, "read"):
			continue
		try:
			rows = _get_rows(doctype, date_field, title_field, from_date, to_date)
		except frappe.PermissionError:
			continue
		for row in rows:
			data.append(
				{
					"deadline_type": label,
					"reference_doctype": doctype,
					"reference": row.name,
					"title": row.get(title_field) or row.get("case_title") or row.name,
					"deadline_date": row.get("deadline_date") if date_field is None else row.get(date_field),
					"status": row.get("status"),
					"owner": row.get("owner") if "owner" in row else None,
				}
			)
	data.sort(key=lambda row: (str(row.get("deadline_date") or ""), row.get("deadline_type") or ""))
	return columns, data


def _get_rows(doctype, date_field, title_field, from_date, to_date):
	fields = ["name", "status"]
	if title_field not in fields:
		fields.append(title_field)
	if doctype == "Contract Obligation":
		fields.extend(["due_date", "next_due_date", "contract"])
		rows = frappe.get_list(
			"Contract Obligation",
			filters={"status": ("in", ["Pending", "In Progress", "Overdue"])},
			fields=fields,
			limit_page_length=5000,
		)
		result = []
		for row in rows:
			date_value = row.get("next_due_date") or row.get("due_date")
			if date_value and getdate(from_date) <= getdate(date_value) <= getdate(to_date):
				row.deadline_date = date_value
				result.append(row)
		return result
	if doctype == "Legal Hearing":
		return frappe.get_list(
			doctype,
			filters={
				"status": "Scheduled",
				date_field: ("between", [from_date, to_date]),
			},
			fields=fields + [date_field, "legal_case", "case_title"],
			limit_page_length=5000,
		)
	if doctype == "Legal Contract":
		return frappe.get_list(
			doctype,
			filters={
				"status": ("in", ["Active", "Expiring"]),
				date_field: ("between", [from_date, to_date]),
			},
			fields=fields + [date_field, "contract_owner"],
			limit_page_length=5000,
		)
	if doctype == "Legal Opinion Request":
		return frappe.get_list(
			doctype,
			filters={
				"status": ("not in", ["Approved", "Rejected", "Closed", "Cancelled"]),
				date_field: ("between", [from_date, to_date]),
			},
			fields=fields + [date_field, "requested_by"],
			limit_page_length=5000,
		)
	if doctype == "Employee Complaints Committee Meeting":
		return frappe.get_list(
			doctype,
			filters={"status": "Scheduled", date_field: ("between", [from_date, to_date])},
			fields=fields + [date_field],
			limit_page_length=5000,
		)
	if doctype == "Legal Correspondence":
		return frappe.get_list(
			doctype,
			filters={
				"status": ("in", ["Under Follow-up", "Received", "Sent"]),
				date_field: ("between", [from_date, to_date]),
			},
			fields=fields + [date_field, "follow_up_owner"],
			limit_page_length=5000,
		)
	if doctype == "Legal Document Register":
		return frappe.get_list(
			doctype,
			filters={
				"status": "Active",
				date_field: ("between", [from_date, to_date]),
			},
			fields=fields + [date_field, "responsible_employee"],
			limit_page_length=5000,
		)
	return []
