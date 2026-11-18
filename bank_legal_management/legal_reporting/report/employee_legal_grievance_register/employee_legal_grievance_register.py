import frappe
from frappe import _


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = [
		{"label": _("الشكوى"), "fieldname": "name", "fieldtype": "Link", "options": "Employee Legal Grievance", "width": 150},
		{"label": _("الموظف"), "fieldname": "employee_name", "fieldtype": "Data", "width": 170},
		{"label": _("العنوان"), "fieldname": "grievance_title", "fieldtype": "Data", "width": 220},
		{"label": _("النوع"), "fieldname": "grievance_type", "fieldtype": "Data", "width": 110},
		{"label": _("جهة الاختصاص"), "fieldname": "jurisdiction_type", "fieldtype": "Data", "width": 180},
		{"label": _("الحالة"), "fieldname": "status", "fieldtype": "Data", "width": 150},
		{"label": _("الأهمية"), "fieldname": "importance", "fieldtype": "Data", "width": 90},
		{"label": _("تاريخ الإحالة"), "fieldname": "referral_date", "fieldtype": "Datetime", "width": 150},
		{"label": _("تاريخ القرار"), "fieldname": "decision_date", "fieldtype": "Date", "width": 110},
		{"label": _("تاريخ الإغلاق"), "fieldname": "closure_date", "fieldtype": "Date", "width": 110},
	]
	filters_dict = {"docstatus": 1}
	if filters.get("from_date") and filters.get("to_date"):
		filters_dict["referral_date"] = ("between", [filters.from_date, filters.to_date])
	elif filters.get("from_date"):
		filters_dict["referral_date"] = (">=", filters.from_date)
	elif filters.get("to_date"):
		filters_dict["referral_date"] = ("<=", filters.to_date)
	for fieldname in ("status", "jurisdiction_type", "grievance_type", "employee", "importance"):
		if filters.get(fieldname):
			filters_dict[fieldname] = filters.get(fieldname)
	return columns, frappe.get_list(
		"Employee Legal Grievance",
		filters=filters_dict,
		fields=[
			"name",
			"employee_name",
			"grievance_title",
			"grievance_type",
			"jurisdiction_type",
			"status",
			"importance",
			"referral_date",
			"decision_date",
			"closure_date",
		],
		order_by="referral_date desc, creation desc",
		limit_page_length=5000,
	)
