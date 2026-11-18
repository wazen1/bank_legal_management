import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, today

from bank_legal_management.utils import get_company, is_system_admin, require_roles

OBLIGATION_ROLES = {
	"Legal Department Manager",
	"Legal Contract Officer",
	"Legal Officer",
}
TERMINAL_STATUSES = {"Completed", "Waived"}


class ContractObligation(Document):
	def before_insert(self):
		if self.status not in (None, "", "Pending"):
			frappe.throw(_("يجب إنشاء الالتزام بحالة معلّق."))
		self.status = "Pending"
		if not self.company and self.contract:
			self.company = frappe.db.get_value("Legal Contract", self.contract, "company")
		self.company = self.company or get_company()

	def validate(self):
		if not self.contract:
			frappe.throw(_("يجب ربط الالتزام بعقد."))
		if not frappe.db.exists("Legal Contract", self.contract):
			frappe.throw(_("العقد المرتبط غير موجود."))
		if not self.description:
			frappe.throw(_("وصف الالتزام مطلوب."))
		if not self.due_date and not self.next_due_date:
			frappe.throw(_("تاريخ الاستحقاق مطلوب."))
		if self.due_date and self.completion_date:
			if getdate(self.completion_date) < getdate(self.due_date):
				frappe.throw(_("تاريخ الإنجاز لا يمكن أن يسبق تاريخ الاستحقاق."))
		self.validate_status_transition()
		if self.status == "Completed" and not self.completion_date:
			self.completion_date = today()

	def validate_status_transition(self):
		before = self.get_doc_before_save()
		if not before or before.status == self.status:
			return
		if self.flags.system_status_update or is_system_admin():
			return
		require_roles(OBLIGATION_ROLES | {"Legal System Administrator"})
		allowed = {
			"Pending": {"In Progress", "Completed", "Overdue", "Waived"},
			"In Progress": {"Completed", "Overdue", "Waived"},
			"Overdue": {"In Progress", "Completed", "Waived"},
			"Completed": set(),
			"Waived": set(),
		}
		if self.status not in allowed.get(before.status, set()):
			frappe.throw(_("انتقال حالة الالتزام غير مسموح."))

	def before_save(self):
		before = self.get_doc_before_save()
		if before and before.status in TERMINAL_STATUSES and before.status == self.status:
			if not is_system_admin():
				for df in self.meta.fields:
					if df.fieldtype in ("Section Break", "Column Break", "Tab Break"):
						continue
					if df.fieldname and self.has_value_changed(df.fieldname):
						frappe.throw(_("الالتزام المكتمل أو المعفى غير قابل للتعديل."), frappe.PermissionError)

	def on_trash(self):
		if self.status != "Pending" and not is_system_admin():
			frappe.throw(_("لا يمكن حذف التزام بعد بدء تنفيذه."), frappe.PermissionError)
