import frappe
from frappe import _
from frappe.model.document import Document

from bank_legal_management.utils import has_any_role, is_system_admin, require_roles


class LegalSettings(Document):
	def validate(self):
		if not is_system_admin() and not has_any_role({"System Manager", "Legal Department Manager"}):
			frappe.throw(
				_("لا يمكن تعديل إعدادات الشؤون القانونية إلا من مدير النظام أو مدير الشؤون القانونية."),
				frappe.PermissionError,
			)
		self.validate_defaults()
		self.validate_alert_days()
		self.validate_governance()

	def validate_defaults(self):
		if not self.default_company:
			self.default_company = frappe.defaults.get_global_default("company")
		if self.default_company:
			company_currency = frappe.db.get_value(
				"Company", self.default_company, "default_currency"
			)
			if company_currency:
				self.default_currency = company_currency
		if not self.default_currency:
			self.default_currency = frappe.defaults.get_defaults().get("currency")

	def validate_alert_days(self):
		fields = (
			"hearing_alert_days",
			"contract_expiry_alert_days",
			"obligation_due_alert_days",
			"opinion_due_alert_days",
			"meeting_alert_days",
			"grievance_stale_days",
		)
		for fieldname in fields:
			value = self.get(fieldname)
			if value is not None and value < 0:
				frappe.throw(_("عدد الأيام في الحقل {0} لا يمكن أن يكون سالبًا.").format(
					_(self.meta.get_label(fieldname))
				))

	def validate_governance(self):
		if not self.committee_quorum_percent:
			self.committee_quorum_percent = 50
		percent = self.committee_quorum_percent
		if percent is not None and not 1 <= percent <= 100:
			frappe.throw(_("نسبة النصاب يجب أن تكون بين 1 و100."))
		if not self.hearing_alert_days:
			self.hearing_alert_days = 3
		if not self.contract_expiry_alert_days:
			self.contract_expiry_alert_days = 30
		if not self.obligation_due_alert_days:
			self.obligation_due_alert_days = 7
		if not self.opinion_due_alert_days:
			self.opinion_due_alert_days = 3
		if not self.meeting_alert_days:
			self.meeting_alert_days = 2
		if not self.grievance_stale_days:
			self.grievance_stale_days = 14

	def on_update(self):
		frappe.clear_cache(doctype="Legal Settings")
