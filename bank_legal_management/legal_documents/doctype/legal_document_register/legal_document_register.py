import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, today

from bank_legal_management.utils import (
	get_employee_for_user,
	is_system_admin,
	require_roles,
)

DOCUMENT_ROLES = {
	"Legal Department Manager",
	"Legal Document Officer",
	"Legal Case Manager",
	"Legal Officer",
}
TERMINAL_STATUSES = {"Archived"}
STATUS_TRANSITIONS = {
	"Draft": {"Active", "Archived"},
	"Active": {"Expired", "Archived"},
	"Expired": {"Active", "Archived"},
	"Archived": set(),
}


class LegalDocumentRegister(Document):
	def before_insert(self):
		if self.status not in (None, "", "Draft"):
			frappe.throw(_("يجب تسجيل المستند بحالة مسودة."))
		self.status = "Draft"
		if not self.document_date:
			self.document_date = today()
		if not self.responsible_employee:
			self.responsible_employee = get_employee_for_user()

	def validate(self):
		if not self.document_title:
			frappe.throw(_("عنوان المستند مطلوب."))
		if not self.document_type:
			frappe.throw(_("نوع المستند مطلوب."))
		if self.expiry_date and self.document_date:
			if getdate(self.expiry_date) < getdate(self.document_date):
				frappe.throw(_("تاريخ انتهاء المستند لا يمكن أن يسبق تاريخ المستند."))
		self.validate_status_transition()
		self.add_version_if_attachment_changed()

	def validate_status_transition(self):
		before = self.get_doc_before_save()
		if before and before.status != self.status:
			if is_system_admin():
				return
			require_roles(DOCUMENT_ROLES | {"Legal System Administrator"})
			if self.status not in STATUS_TRANSITIONS.get(before.status, set()):
				frappe.throw(
					_("انتقال حالة المستند من {0} إلى {1} غير مسموح.").format(
						before.status, self.status
					)
				)
		if self.status == "Active" and self.expiry_date and getdate(self.expiry_date) < getdate(today()):
			frappe.throw(_("لا يمكن تفعيل مستند انتهت صلاحيته."))

	def add_version_if_attachment_changed(self):
		before = self.get_doc_before_save()
		if not self.attachment:
			return
		attachment_changed = not before or before.attachment != self.attachment
		if not attachment_changed:
			return
		self.append(
			"versions",
			{
				"version_no": len(self.versions) + 1,
				"version_date": today(),
				"attachment": self.attachment,
				"uploaded_by": frappe.session.user,
			},
		)

	def before_save(self):
		before = self.get_doc_before_save()
		if before and before.status in TERMINAL_STATUSES and before.status == self.status:
			if not is_system_admin():
				for df in self.meta.fields:
					if df.fieldtype in ("Section Break", "Column Break", "Tab Break"):
						continue
					if df.fieldname and self.has_value_changed(df.fieldname):
						frappe.throw(_("المستند المؤرشف غير قابل للتعديل."), frappe.PermissionError)

	def on_trash(self):
		if self.status != "Draft" and not is_system_admin():
			frappe.throw(_("لا يمكن حذف مستند مسجل."), frappe.PermissionError)
