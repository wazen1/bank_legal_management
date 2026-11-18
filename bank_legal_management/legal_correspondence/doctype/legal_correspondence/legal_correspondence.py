import frappe
from frappe import _
from frappe.model.document import Document

from bank_legal_management.utils import (
	get_employee_for_user,
	is_system_admin,
	require_roles,
)

CORRESPONDENCE_ROLES = {
	"Legal Department Manager",
	"Legal Document Officer",
	"Legal Case Manager",
	"Legal Officer",
	"Legal Contract Officer",
	"Legal Opinion Officer",
}
TERMINAL_STATUSES = {"Closed"}
STATUS_TRANSITIONS = {
	"Draft": {"Received", "Sent", "Under Follow-up"},
	"Received": {"Under Follow-up", "Closed"},
	"Sent": {"Under Follow-up", "Closed"},
	"Under Follow-up": {"Closed"},
	"Closed": set(),
}


class LegalCorrespondence(Document):
	def before_insert(self):
		if self.status not in (None, "", "Draft"):
			frappe.throw(_("يجب إنشاء المراسلة بحالة مسودة."))
		self.status = "Draft"
		if not self.correspondence_date:
			self.correspondence_date = frappe.utils.today()
		if not self.follow_up_owner:
			self.follow_up_owner = get_employee_for_user()

	def validate(self):
		if not self.subject:
			frappe.throw(_("موضوع المراسلة مطلوب."))
		if not self.correspondence_type:
			frappe.throw(_("نوع المراسلة مطلوب."))
		self.validate_status_transition()
		if self.status == "Under Follow-up" and not self.follow_up_owner:
			frappe.throw(_("يجب تحديد مسؤول المتابعة."))

	def validate_status_transition(self):
		before = self.get_doc_before_save()
		if not before or before.status == self.status:
			return
		if is_system_admin():
			return
		require_roles(CORRESPONDENCE_ROLES | {"Legal System Administrator"})
		if self.status not in STATUS_TRANSITIONS.get(before.status, set()):
			frappe.throw(
				_("انتقال حالة المراسلة من {0} إلى {1} غير مسموح.").format(
					before.status, self.status
				)
			)

	def before_save(self):
		before = self.get_doc_before_save()
		if before and before.status in TERMINAL_STATUSES and before.status == self.status:
			if not is_system_admin():
				for df in self.meta.fields:
					if df.fieldtype in ("Section Break", "Column Break", "Tab Break"):
						continue
					if df.fieldname and self.has_value_changed(df.fieldname):
						frappe.throw(_("المراسلة المغلقة غير قابلة للتعديل."), frappe.PermissionError)

	def on_trash(self):
		if self.status != "Draft" and not is_system_admin():
			frappe.throw(_("لا يمكن حذف مراسلة مسجلة."), frappe.PermissionError)
