import frappe
from frappe import _
from frappe.model.document import Document


class GrievanceActionLog(Document):
	def validate(self):
		if self.is_new():
			if not self.grievance:
				frappe.throw(_("سجل الإجراء يجب أن يرتبط بشكوى."))
			docstatus = frappe.db.get_value("Employee Legal Grievance", self.grievance, "docstatus")
			if docstatus != 1:
				frappe.throw(_("لا يمكن تسجيل إجراء على شكوى غير مقدمة."))
			self.is_system_generated = 1
			self.performed_by = self.performed_by or frappe.session.user
			self.action_time = self.action_time or frappe.utils.now_datetime()

	def on_update(self):
		if (
			not self.flags.in_insert
			and not frappe.flags.in_install
			and not frappe.flags.in_migrate
		):
			frappe.throw(
				_("سجل إجراءات الشكوى غير قابل للتعديل. استخدم إجراء جديدًا موثقًا."),
				frappe.PermissionError,
			)

	def on_trash(self):
		if not frappe.flags.in_install and not frappe.flags.in_migrate:
			frappe.throw(
				_("سجل إجراءات الشكوى غير قابل للحذف."),
				frappe.PermissionError,
			)
