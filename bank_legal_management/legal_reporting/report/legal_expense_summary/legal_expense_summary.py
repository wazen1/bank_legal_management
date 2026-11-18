import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = [
		{"label": _("نوع المصروف"), "fieldname": "expense_type", "fieldtype": "Data", "width": 150},
		{"label": _("الحالة"), "fieldname": "status", "fieldtype": "Data", "width": 130},
		{"label": _("العدد"), "fieldname": "count", "fieldtype": "Int", "width": 80},
		{"label": _("الإجمالي"), "fieldname": "total_amount", "fieldtype": "Currency", "width": 150},
		{"label": _("العملة"), "fieldname": "currency", "fieldtype": "Data", "width": 80},
	]
	filters_dict = {}
	if filters.get("from_date"):
		filters_dict["expense_date"] = (">=", filters.from_date)
	if filters.get("to_date"):
		if "expense_date" in filters_dict:
			filters_dict["expense_date"] = ("between", [filters.from_date, filters.to_date])
		else:
			filters_dict["expense_date"] = ("<=", filters.to_date)
	for fieldname in ("status", "expense_type", "company"):
		if filters.get(fieldname):
			filters_dict[fieldname] = filters.get(fieldname)
	rows = frappe.get_list(
		"Legal Expense",
		filters=filters_dict,
		fields=["expense_type", "status", "amount", "currency"],
		limit_page_length=5000,
	)
	buckets = {}
	for row in rows:
		key = (row.expense_type or "", row.status or "", row.currency or "")
		bucket = buckets.setdefault(key, {"count": 0, "total_amount": 0.0})
		bucket["count"] += 1
		bucket["total_amount"] += flt(row.amount)
	data = [
		{
			"expense_type": key[0],
			"status": key[1],
			"currency": key[2],
			"count": value["count"],
			"total_amount": value["total_amount"],
		}
		for key, value in buckets.items()
	]
	data.sort(key=lambda row: (row["expense_type"], row["status"], row["currency"]))
	return columns, data
