import frappe
from frappe import _


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = [
		{"label": _("القضية"), "fieldname": "name", "fieldtype": "Link", "options": "Legal Case", "width": 150},
		{"label": _("العنوان"), "fieldname": "case_title", "fieldtype": "Data", "width": 220},
		{"label": _("النوع"), "fieldname": "case_type", "fieldtype": "Data", "width": 100},
		{"label": _("الحالة"), "fieldname": "status", "fieldtype": "Data", "width": 120},
		{"label": _("المحكمة/الجهة"), "fieldname": "court_or_authority", "fieldtype": "Data", "width": 160},
		{"label": _("المسؤول"), "fieldname": "assigned_officer", "fieldtype": "Link", "options": "Employee", "width": 150},
		{"label": _("تاريخ التسجيل"), "fieldname": "registration_date", "fieldtype": "Date", "width": 110},
		{"label": _("الجلسة القادمة"), "fieldname": "next_hearing_date", "fieldtype": "Date", "width": 110},
		{"label": _("قيمة المطالبة"), "fieldname": "claim_amount", "fieldtype": "Currency", "width": 120},
		{"label": _("الشركة"), "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 130},
	]
	filters_dict = {}
	if filters.get("from_date"):
		filters_dict["registration_date"] = (">=", filters.from_date)
	if filters.get("to_date"):
		if "registration_date" in filters_dict:
			filters_dict["registration_date"] = (
				"between",
				[filters.from_date, filters.to_date],
			)
		else:
			filters_dict["registration_date"] = ("<=", filters.to_date)
	for fieldname in ("status", "case_type", "company", "assigned_officer"):
		if filters.get(fieldname):
			filters_dict[fieldname] = filters.get(fieldname)
	return columns, frappe.get_list(
		"Legal Case",
		filters=filters_dict,
		fields=[
			"name",
			"case_title",
			"case_type",
			"status",
			"court_or_authority",
			"assigned_officer",
			"registration_date",
			"next_hearing_date",
			"claim_amount",
			"company",
		],
		order_by="registration_date desc, creation desc",
		limit_page_length=5000,
	)
