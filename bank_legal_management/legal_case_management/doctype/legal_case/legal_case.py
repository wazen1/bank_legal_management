import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, today

from bank_legal_management.utils import (
	get_employee_for_user,
	get_user_for_employee,
	has_any_role,
	is_system_admin,
	notify_status_change,
	require_roles,
)

CASE_ROLES = {
	"Legal Department Manager",
	"Legal Case Manager",
	"Legal Officer",
}
MANAGER_ROLES = {"Legal Department Manager", "Legal System Administrator"}
TERMINAL_STATUSES = {"Closed", "Archived"}
STATUS_TRANSITIONS = {
	"Draft": {"Registered", "Under Review"},
	"Registered": {"Under Review", "Assigned", "In Progress", "Awaiting Documents"},
	"Under Review": {"Assigned", "In Progress", "Awaiting Documents"},
	"Assigned": {"In Progress", "Awaiting Documents", "Hearing Scheduled"},
	"In Progress": {
		"Hearing Scheduled",
		"Awaiting Documents",
		"Awaiting Judgment",
		"Settled",
		"Closed",
	},
	"Hearing Scheduled": {
		"In Progress",
		"Awaiting Documents",
		"Awaiting Judgment",
		"Settled",
	},
	"Awaiting Documents": {"In Progress", "Hearing Scheduled", "Awaiting Judgment"},
	"Awaiting Judgment": {"Judgment Issued", "Settled"},
	"Judgment Issued": {"Under Appeal", "Settled", "Closed"},
	"Under Appeal": {"Judgment Issued", "Settled", "Closed"},
	"Settled": {"Closed"},
	"Closed": {"Archived"},
	"Archived": set(),
}


class LegalCase(Document):
	def before_insert(self):
		if self.status not in (None, "", "Draft"):
			frappe.throw(_("يجب إنشاء قضية جديدة بحالة مسودة."))
		self.status = "Draft"
		if not self.company:
			self.company = frappe.defaults.get_global_default("company")

	def validate(self):
		self.validate_dates()
		self.validate_amounts()
		self.validate_assignment()
		self.validate_status_transition()
		before = self.get_doc_before_save()
		self.flags.previous_status = before.status if before else None
		self.set_status_dates()
		self.sync_hearing_dates()
		if (
			self.status == "Hearing Scheduled"
			and (not before or before.status != "Hearing Scheduled")
			and not self.next_hearing_date
		):
			frappe.throw(_("لا يمكن تعيين حالة الجلسة المجدولة دون جلسة قادمة."))

	def validate_dates(self):
		for fieldname in ("filing_date", "registration_date", "closure_date", "archive_date"):
			value = self.get(fieldname)
			if value and getdate(value) > getdate(today()) and fieldname in (
				"closure_date",
				"archive_date",
			):
				frappe.throw(_("لا يمكن أن يكون التاريخ المستقبلي للقفل أو الأرشفة."))
		if self.filing_date and self.registration_date and getdate(self.filing_date) > getdate(
			self.registration_date
		):
			frappe.throw(_("تاريخ رفع القضية لا يمكن أن يتجاوز تاريخ التسجيل."))
		if self.filing_date and self.closure_date and getdate(self.filing_date) > getdate(
			self.closure_date
		):
			frappe.throw(_("تاريخ رفع القضية لا يمكن أن يتجاوز تاريخ الإغلاق."))

	def validate_amounts(self):
		if self.claim_amount is not None and self.claim_amount < 0:
			frappe.throw(_("قيمة المطالبة لا يمكن أن تكون سالبة."))

	def validate_assignment(self):
		if self.assigned_officer:
			status = frappe.db.get_value("Employee", self.assigned_officer, "status")
			if status != "Active":
				frappe.throw(_("يجب أن يكون مسؤول القضية موظفًا نشطًا."))
		if self.status == "Assigned" and not self.assigned_officer:
			frappe.throw(_("يجب تحديد مسؤول القضية قبل تعيينها."))

	def validate_status_transition(self):
		before = self.get_doc_before_save()
		if not before or before.status == self.status:
			return
		if self.flags.system_status_update or is_system_admin():
			return
		require_roles(CASE_ROLES | MANAGER_ROLES)
		old_status = before.status
		allowed = set(STATUS_TRANSITIONS.get(old_status, set()))
		if old_status in TERMINAL_STATUSES:
			allowed = set()
		if old_status in ("Registered", "Under Review", "Assigned", "In Progress") and self.status in (
			"Closed",
			"Archived",
		):
			require_roles(MANAGER_ROLES)
			allowed.add(self.status)
		if self.status not in allowed:
			frappe.throw(
				_("انتقال حالة القضية من {0} إلى {1} غير مسموح.").format(old_status, self.status)
			)
		if self.status == "Archived" and old_status != "Closed":
			frappe.throw(_("لا يمكن أرشفة القضية قبل إغلاقها."))

	def set_status_dates(self):
		if self.status == "Registered" and not self.registration_date:
			self.registration_date = today()
		if self.status == "Closed" and not self.closure_date:
			self.closure_date = today()
		if self.status == "Archived" and not self.archive_date:
			self.archive_date = today()

	def sync_hearing_dates(self):
		if not self.name and not self.get("__islocal"):
			return
		if frappe.db.exists("DocType", "Legal Hearing") is False:
			return
		next_date = frappe.db.sql(
			"""
			SELECT MIN(hearing_date) FROM `tabLegal Hearing`
			WHERE legal_case = %s AND status = 'Scheduled'
				AND hearing_date >= %s
			""",
			(self.name, today()),
		)
		last_date = frappe.db.sql(
			"""
			SELECT MAX(hearing_date) FROM `tabLegal Hearing`
			WHERE legal_case = %s AND status = 'Completed'
			""",
			(self.name,),
		)
		self.next_hearing_date = next_date[0][0] if next_date and next_date[0][0] else None
		self.last_hearing_date = last_date[0][0] if last_date and last_date[0][0] else None

	def before_save(self):
		before = self.get_doc_before_save()
		if before and before.status in TERMINAL_STATUSES and self.status == before.status:
			if not is_system_admin():
				for df in self.meta.fields:
					if df.fieldtype in ("Section Break", "Column Break", "Tab Break"):
						continue
					if df.fieldname in ("status",):
						continue
					if df.fieldname and self.has_value_changed(df.fieldname):
						frappe.throw(
							_("القضية المغلقة أو المؤرشفة غير قابلة للتعديل."),
							frappe.PermissionError,
						)

	def on_update(self):
		if self.flags.previous_status and self.flags.previous_status != self.status:
			notify_status_change(self, subject=_("تحديث حالة قضية قانونية"))

	def on_trash(self):
		if self.status != "Draft" and not is_system_admin():
			frappe.throw(
				_("لا يمكن حذف قضية إلا من مدير النظام القانوني."),
				frappe.PermissionError,
			)

	@frappe.whitelist()
	def get_case_summary(self):
		self.check_permission("read")
		hearings = frappe.get_all(
			"Legal Hearing",
			filters={"legal_case": self.name},
			fields=["name", "hearing_date", "status", "hearing_type"],
			order_by="hearing_date desc",
			limit=20,
		)
		return {
			"name": self.name,
			"status": self.status,
			"next_hearing_date": self.next_hearing_date,
			"last_hearing_date": self.last_hearing_date,
			"hearings": hearings,
		}
