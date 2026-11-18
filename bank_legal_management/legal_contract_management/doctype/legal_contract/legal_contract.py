import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, now_datetime, today

from bank_legal_management.utils import (
	get_company,
	get_default_currency,
	get_employee_for_user,
	get_settings,
	has_any_role,
	is_system_admin,
	notify_status_change,
	require_roles,
)

CONTRACT_ROLES = {
	"Legal Department Manager",
	"Legal Contract Officer",
	"Legal Officer",
}
MANAGER_ROLES = {"Legal Department Manager", "Legal System Administrator"}
TERMINAL_STATUSES = {"Terminated", "Expired", "Archived"}
STATUS_TRANSITIONS = {
	"Draft": {"Under Legal Review"},
	"Under Legal Review": {"Returned for Amendment", "Pending Approval"},
	"Returned for Amendment": {"Under Legal Review"},
	"Pending Approval": {"Pending Signature", "Returned for Amendment"},
	"Pending Signature": {"Active"},
	"Active": {"Expiring", "Terminated", "Expired"},
	"Expiring": {"Active", "Terminated", "Expired", "Renewed"},
	"Renewed": {"Archived"},
	"Terminated": {"Archived"},
	"Expired": {"Archived"},
	"Archived": set(),
}
ACTION_BY_STATUS = {
	"Under Legal Review": "Legal Review",
	"Pending Approval": "Approval",
	"Pending Signature": "Signature",
	"Active": "Activation",
	"Terminated": "Termination",
	"Renewed": "Renewal",
	"Archived": "Archive",
	"Expired": "Status Change",
	"Expiring": "Status Change",
}


class LegalContract(Document):
	def before_insert(self):
		if self.status not in (None, "", "Draft"):
			frappe.throw(_("يجب إنشاء عقد جديد بحالة مسودة."))
		self.status = "Draft"
		self.company = self.company or get_company()
		self.currency = self.currency or get_default_currency(self.company)
		if not self.contract_owner:
			self.contract_owner = get_employee_for_user()

	def validate(self):
		self.validate_dates()
		self.validate_amount()
		self.validate_party()
		self.validate_owner()
		before = self.get_doc_before_save()
		self.flags.previous_status = before.status if before else None
		self.validate_status_transition(before)
		self.validate_status_requirements()
		if before and before.status != self.status:
			self.append_approval_history(before.status)
		self.flags.previous_status = before.status if before else None

	def validate_dates(self):
		for fieldname in ("start_date", "end_date", "signature_date"):
			value = self.get(fieldname)
			if value and getdate(value) > getdate(today()) and fieldname == "signature_date":
				frappe.throw(_("تاريخ التوقيع لا يمكن أن يكون في المستقبل."))
		if self.start_date and self.end_date:
			if getdate(self.start_date) > getdate(self.end_date):
				frappe.throw(_("تاريخ بداية العقد يجب أن يسبق تاريخ نهايته."))
		if self.terminated_on and self.start_date and getdate(self.terminated_on) < getdate(
			self.start_date
		):
			frappe.throw(_("تاريخ الإنهاء لا يمكن أن يسبق تاريخ بداية العقد."))

	def validate_amount(self):
		if self.contract_value is not None and self.contract_value < 0:
			frappe.throw(_("قيمة العقد لا يمكن أن تكون سالبة."))

	def validate_party(self):
		if not self.contract_title:
			frappe.throw(_("عنوان العقد مطلوب."))
		if self.party and not self.party_type:
			frappe.throw(_("يجب تحديد نوع الطرف المرتبط بالعقد."))

	def validate_owner(self):
		if self.contract_owner:
			if frappe.db.get_value("Employee", self.contract_owner, "status") != "Active":
				frappe.throw(_("يجب أن يكون مسؤول العقد موظفًا نشطًا."))

	def validate_status_transition(self, before):
		if not before or before.status == self.status:
			return
		if self.flags.system_status_update or is_system_admin():
			return
		require_roles(CONTRACT_ROLES | MANAGER_ROLES)
		if before.status in TERMINAL_STATUSES:
			allowed = set()
		else:
			allowed = set(STATUS_TRANSITIONS.get(before.status, set()))
		if self.status not in allowed:
			frappe.throw(
				_("انتقال حالة العقد من {0} إلى {1} غير مسموح.").format(
					before.status, self.status
				)
			)
		if self.status == "Archived" and before.status not in (
			"Terminated",
			"Expired",
			"Renewed",
		):
			frappe.throw(_("لا يمكن أرشفة العقد قبل إنهائه أو انتهائه أو تجديده."))

	def validate_status_requirements(self):
		settings = get_settings()
		if self.status in (
			"Under Legal Review",
			"Pending Approval",
			"Pending Signature",
			"Active",
		):
			if not self.party:
				frappe.throw(_("يجب تحديد الطرف المرتبط بالعقد قبل إحالة العقد للمراجعة."))
			if not self.party_name:
				frappe.throw(_("يجب تسجيل اسم الطرف المرتبط بالعقد."))
		if self.status == "Active":
			if not self.start_date or not self.end_date:
				frappe.throw(_("يجب تحديد تاريخ بداية ونهاية العقد قبل التفعيل."))
			if settings.get("contract_activation_requires_signature"):
				if not self.signed_contract:
					frappe.throw(_("لا يمكن تفعيل العقد دون إرفاق النسخة الموقعة."))
				if not self.signature_date:
					frappe.throw(_("لا يمكن تفعيل العقد دون تاريخ التوقيع."))
			self.approved_by = self.approved_by or frappe.session.user
			self.approval_date = self.approval_date or today()
			if self.end_date and getdate(self.end_date) < getdate(today()):
				frappe.throw(_("لا يمكن تفعيل عقد انتهت مدته."))
		if self.status == "Terminated":
			if not self.termination_reason:
				frappe.throw(_("سبب إنهاء العقد مطلوب."))
			if not self.terminated_on:
				self.terminated_on = today()
		if self.status == "Expired" and not self.end_date:
			frappe.throw(_("لا يمكن تعيين العقد كمنتهٍ دون تاريخ نهاية."))

	def append_approval_history(self, from_status):
		action = ACTION_BY_STATUS.get(self.status, "Status Change")
		self.append(
			"approval_history",
			{
				"action": action,
				"action_by": frappe.session.user,
				"action_on": now_datetime(),
				"from_status": from_status,
				"to_status": self.status,
			},
		)

	def before_save(self):
		before = self.get_doc_before_save()
		if before and before.status in TERMINAL_STATUSES and before.status == self.status:
			if not is_system_admin() and not self.flags.system_status_update:
				for df in self.meta.fields:
					if df.fieldtype in ("Section Break", "Column Break", "Tab Break"):
						continue
					if df.fieldname == "status":
						continue
					if df.fieldname and self.has_value_changed(df.fieldname):
						frappe.throw(
							_("العقد المنتهي أو المؤرشف غير قابل للتعديل."),
							frappe.PermissionError,
						)

	def on_update(self):
		if self.flags.previous_status and self.flags.previous_status != self.status:
			notify_status_change(self, subject=_("تحديث حالة عقد قانوني"))

	def on_trash(self):
		if self.status not in ("Draft", "Returned for Amendment") and not is_system_admin():
			frappe.throw(
				_("لا يمكن حذف عقد بعد اعتماده إلا من مدير النظام القانوني."),
				frappe.PermissionError,
			)

	@frappe.whitelist()
	def get_contract_summary(self):
		self.check_permission("read")
		obligations = frappe.get_all(
			"Contract Obligation",
			filters={"contract": self.name},
			fields=["name", "description", "due_date", "next_due_date", "status"],
			order_by="COALESCE(next_due_date, due_date) asc",
		)
		return {
			"name": self.name,
			"status": self.status,
			"start_date": self.start_date,
			"end_date": self.end_date,
			"obligations": obligations,
		}
