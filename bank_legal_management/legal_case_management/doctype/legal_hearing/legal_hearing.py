import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, today

from bank_legal_management.utils import (
	has_any_role,
	is_system_admin,
	notify_status_change,
	notify_users,
	require_roles,
)

HEARING_ROLES = {
	"Legal Department Manager",
	"Legal Case Manager",
	"Legal Officer",
}
TERMINAL_STATUSES = {"Completed", "Cancelled"}


class LegalHearing(Document):
	def before_insert(self):
		if not self.legal_case:
			frappe.throw(_("يجب ربط الجلسة بقضية."))
		if self.status not in (None, "", "Scheduled"):
			frappe.throw(_("يجب إنشاء الجلسة بحالة مجدولة."))
		self.status = "Scheduled"
		case = frappe.get_doc("Legal Case", self.legal_case)
		self.case_title = case.case_title
		self.confidentiality = case.confidentiality
		self.court_or_authority = self.court_or_authority or case.court_or_authority
		if not self.hearing_date:
			frappe.throw(_("تاريخ الجلسة مطلوب."))
		if getdate(self.hearing_date) < getdate(today()):
			frappe.throw(_("لا يمكن جدولة جلسة بتاريخ ماضٍ."))

	def validate(self):
		if not self.legal_case:
			frappe.throw(_("يجب ربط الجلسة بقضية."))
		if not frappe.db.exists("Legal Case", self.legal_case):
			frappe.throw(_("القضية المرتبطة غير موجودة."))
		if not self.hearing_date:
			frappe.throw(_("تاريخ الجلسة مطلوب."))
		if self.hearing_time and self.next_action_date and getdate(self.next_action_date) < getdate(
			self.hearing_date
		):
			frappe.throw(_("تاريخ الإجراء التالي لا يمكن أن يسبق تاريخ الجلسة."))
		self.validate_status_transition()
		if self.status == "Completed" and not self.outcome:
			frappe.throw(_("نتيجة الجلسة مطلوبة قبل تعيينها كمكتملة."))
		if self.status == "Postponed" and not self.next_action:
			frappe.throw(_("يجب توثيق الإجراء التالي عند تأجيل الجلسة."))
		if not is_system_admin() and self.status in TERMINAL_STATUSES:
			before = self.get_doc_before_save()
			if before and before.status in TERMINAL_STATUSES:
				frappe.throw(_("لا يمكن تعديل جلسة مكتملة أو ملغاة."))

	def validate_status_transition(self):
		before = self.get_doc_before_save()
		if before and before.status != self.status:
			if not self.flags.system_status_update and not is_system_admin():
				require_roles(HEARING_ROLES)
				allowed = {
					"Scheduled": {"Completed", "Postponed", "Cancelled"},
					"Postponed": {"Scheduled", "Cancelled"},
					"Completed": {"Scheduled"},
					"Cancelled": {"Scheduled"},
				}
				if self.status not in allowed.get(before.status, set()):
					frappe.throw(_("انتقال حالة الجلسة غير مسموح."))

	def on_update(self):
		self.sync_case()
		before = self.get_doc_before_save()
		if (not before or before.status != self.status) and self.status == "Scheduled":
			case = frappe.get_doc("Legal Case", self.legal_case)
			recipients = set()
			if case.assigned_officer:
				user = frappe.db.get_value("Employee", case.assigned_officer, "user_id")
				if user:
					recipients.add(user)
			notify_users(recipients, self.doctype, self.name, _("تم جدولة جلسة قانونية"))

	def after_insert(self):
		self.sync_case()

	def on_trash(self):
		if self.status == "Completed" and not is_system_admin():
			frappe.throw(_("لا يمكن حذف جلسة مكتملة."), frappe.PermissionError)
		self.sync_case()

	def sync_case(self):
		if not self.legal_case:
			return
		case = frappe.get_doc("Legal Case", self.legal_case)
		case.flags.system_status_update = True
		case.flags.system_hearing_sync = True
		case.save(ignore_permissions=True)
