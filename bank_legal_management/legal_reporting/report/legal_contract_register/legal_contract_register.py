import frappe
from frappe import _


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = [
		{"label": _("العقد"), "fieldname": "name", "fieldtype": "Link", "options": "Legal Contract", "width": 150},
		{"label": _("العنوان"), "fieldname": "contract_title", "fieldtype": "Data", "width": 220},
		{"label": _("النوع"), "fieldname": "contract_type", "fieldtype": "Data", "width": 100},
		{"label": _("الحالة"), "fieldname": "status", "fieldtype": "Data", "width": 130},
		{"label": _("الطرف"), "fieldname": "party_name", "fieldtype": "Data", "width": 170},
		{"label": _("المسؤول"), "fieldname": "contract_owner", "fieldtype": "Link", "options": "Employee", "width": 150},
		{"label": _("تاريخ البداية"), "fieldname": "start_date", "fieldtype": "Date", "width": 110},
		{"label": _("تاريخ النهاية"), "fieldname": "end_date", "fieldtype": "Date", "width": 110},
		{"label": _("القيمة"), "fieldname": "contract_value", "fieldtype": "Currency", "width": 130},
		{"label": _("العملة"), "fieldname": "currency", "fieldtype": "Link", "options": "Currency", "width": 80},
	]
	filters_dict = {}
	if filters.get("from_date") and filters.get("to_date"):
		filters_dict["end_date"] = ("between", [filters.from_date, filters.to_date])
	elif filters.get("from_date"):
		filters_dict["end_date"] = (">=", filters.from_date)
	elif filters.get("to_date"):
		filters_dict["end_date"] = ("<=", filters.to_date)
	for fieldname in ("status", "contract_type", "company", "contract_owner"):
		if filters.get(fieldname):
			filters_dict[fieldname] = filters.get(fieldname)
	return columns, frappe.get_list(
		"Legal Contract",
		filters=filters_dict,
		fields=[
			"name",
			"contract_title",
			"contract_type",
			"status",
			"party_name",
			"contract_owner",
			"start_date",
			"end_date",
			"contract_value",
			"currency",
			"company",
		],
		order_by="end_date asc, creation desc",
		limit_page_length=5000,
	)
