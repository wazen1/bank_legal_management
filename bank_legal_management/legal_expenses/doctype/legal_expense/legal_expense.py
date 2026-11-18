import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import today

from bank_legal_management.utils import (
	get_company,
	get_default_currency,
	is_system_admin,
	require_roles,
)

EXPENSE_ROLES = {
	"Legal Department Manager",
	"Legal Expense Officer",
	"Legal Officer",
}
APPROVER_ROLES = {"Legal Department Manager", "Legal System Administrator"}
TERMINAL_STATUSES = {"Paid", "Rejected", "Cancelled"}
STATUS_TRANSITIONS = {
	"Draft": {"Pending Review", "Cancelled"},
	"Pending Review": {"Approved", "Rejected", "Draft"},
	"Approved": {"Paid", "Rejected"},
	"Rejected": set(),
	"Paid": set(),
	"Cancelled": set(),
}


class LegalExpense(Document):
	def before_insert(self):
		if self.status not in (None, "", "Draft"):
			frappe.throw(_("يجب إنشاء المصروف بحالة مسودة."))
		self.status = "Draft"
		self.company = self.company or get_company()
		self.currency = self.currency or get_default_currency(self.company)

	def validate(self):
		if not self.expense_date:
			frappe.throw(_("تاريخ المصروف مطلوب."))
		if not self.expense_type:
			frappe.throw(_("نوع المصروف مطلوب."))
		if not self.description:
			frappe.throw(_("وصف المصروف مطلوب."))
		if self.amount is None or self.amount <= 0:
			frappe.throw(_("قيمة المصروف يجب أن تكون أكبر من صفر."))
		self.validate_status_transition()
		if self.status == "Approved":
			self.approved_by = self.approved_by or frappe.session.user
			self.approval_date = self.approval_date or today()
		if self.status == "Pending Review":
			self.reviewed_by = self.reviewed_by or frappe.session.user
			self.review_date = self.review_date or today()
		if self.status == "Rejected" and not self.rejection_reason:
			frappe.throw(_("سبب رفض المصروف مطلوب."))

	def validate_status_transition(self):
		before = self.get_doc_before_save()
		if not before or before.status == self.status:
			return
		if is_system_admin():
			return
		require_roles(EXPENSE_ROLES)
		if self.status == "Approved" and not set(frappe.get_roles()).intersection(APPROVER_ROLES):
			frappe.throw(_("اعتماد المصروف يتطلب مدير الشؤون القانونية."), frappe.PermissionError)
		if self.status not in STATUS_TRANSITIONS.get(before.status, set()):
			frappe.throw(
				_("انتقال حالة المصروف من {0} إلى {1} غير مسموح.").format(
					before.status, self.status
				)
			)
		if before.status in TERMINAL_STATUSES:
			frappe.throw(_("لا يمكن تعديل حالة مصروف نهائي."))

	def before_save(self):
		before = self.get_doc_before_save()
		if before and before.status in TERMINAL_STATUSES and before.status == self.status:
			if not is_system_admin():
				for df in self.meta.fields:
					if df.fieldtype in ("Section Break", "Column Break", "Tab Break"):
						continue
					if df.fieldname == "status":
						continue
					if df.fieldname and self.has_value_changed(df.fieldname):
						frappe.throw(_("المصروف النهائي غير قابل للتعديل."), frappe.PermissionError)

	def on_trash(self):
		if self.status != "Draft" and not is_system_admin():
			frappe.throw(_("لا يمكن حذف مصروف بعد بدء مراجعته."), frappe.PermissionError)

	def _set_status(self, status, **updates):
		previous = self.status
		for fieldname, value in updates.items():
			self.set(fieldname, value)
		self.status = status
		self.save(ignore_permissions=True)
		return previous

	@frappe.whitelist()
	def submit_for_review(self):
		self.check_permission("read")
		if self.status != "Draft":
			frappe.throw(_("لا يمكن إرسال المصروف للمراجعة في الحالة الحالية."))
		require_roles(EXPENSE_ROLES)
		self._set_status(
			"Pending Review",
			reviewed_by=frappe.session.user,
			review_date=today(),
		)
		return {"name": self.name, "status": self.status}

	@frappe.whitelist()
	def approve_expense(self):
		self.check_permission("read")
		if self.status != "Pending Review":
			frappe.throw(_("المصروف ليس قيد المراجعة."))
		require_roles(APPROVER_ROLES)
		self._set_status(
			"Approved",
			approved_by=frappe.session.user,
			approval_date=today(),
		)
		return {"name": self.name, "status": self.status}

	@frappe.whitelist()
	def reject_expense(self, rejection_reason):
		self.check_permission("read")
		if self.status not in ("Pending Review", "Approved"):
			frappe.throw(_("لا يمكن رفض المصروف في الحالة الحالية."))
		require_roles(APPROVER_ROLES)
		reason = (rejection_reason or "").strip()
		if not reason:
			frappe.throw(_("سبب الرفض مطلوب."))
		self._set_status("Rejected", rejection_reason=reason)
		return {"name": self.name, "status": self.status}

	@frappe.whitelist()
	def mark_paid(self):
		self.check_permission("read")
		if self.status != "Approved":
			frappe.throw(_("لا يمكن تعليم المصروف كمدفوع قبل اعتماده."))
		require_roles(EXPENSE_ROLES)
		self._set_status("Paid")
		return {"name": self.name, "status": self.status}

	@frappe.whitelist()
	def cancel_expense(self):
		self.check_permission("read")
		if self.status not in ("Draft", "Pending Review"):
			frappe.throw(_("لا يمكن إلغاء المصروف في الحالة الحالية."))
		require_roles(EXPENSE_ROLES)
		self._set_status("Cancelled")
		return {"name": self.name, "status": self.status}

	@frappe.whitelist()
	def get_expense_summary(self):
		self.check_permission("read")
		from frappe.utils import flt

		return {
			"name": self.name,
			"status": self.status,
			"amount": flt(self.amount),
			"currency": self.currency,
			"accounting_voucher": self.accounting_voucher,
		}
