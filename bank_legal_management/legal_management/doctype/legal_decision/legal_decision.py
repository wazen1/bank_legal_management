import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime, today

from bank_legal_management.utils import has_any_role, is_system_admin

DECISION_ROLE = "Authorized Decision Maker"
FINAL_STATUSES = {"Approved", "Rejected", "Implemented", "Archived"}


class LegalDecision(Document):
	def before_insert(self):
		if self.status not in (None, "", "Draft Recommendation") and not self.flags.decision_internal_approval:
			frappe.throw(_("لا يمكن إنشاء قرار بحالة نهائية مباشرة."))
		if not self.flags.decision_internal_approval:
			self.status = "Draft Recommendation"
		self.prepared_by = self.prepared_by or frappe.session.user
		self.recorded_by = frappe.session.user
		self.recorded_on = now_datetime()
		if not self.referred_on:
			self.referred_on = now_datetime()

	def validate(self):
		self.validate_reference()
		self.validate_separation()
		self.validate_status_transition()
		self.validate_final_fields()
		self.recorded_by = self.recorded_by or frappe.session.user
		self.recorded_on = self.recorded_on or now_datetime()

	def validate_reference(self):
		if self.decision_type == "Employee Legal Grievance":
			if not self.reference_name:
				frappe.throw(_("يجب اختيار الشكوى المرتبطة بالقرار."))
			if frappe.db.get_value("Employee Legal Grievance", self.reference_name, "docstatus") != 1:
				frappe.throw(_("يجب أن تكون الشكوى المرتبطة مقدمة قبل إصدار القرار."))
		if self.reference_doctype and self.reference_name:
			if not frappe.db.exists(self.reference_doctype, self.reference_name):
				frappe.throw(_("السجل المرجعي للقرار غير موجود."))
		if self.decision_type in ("Case", "Contract", "Legal Opinion", "Employee Legal Grievance"):
			if not self.reference_name:
				frappe.throw(_("نوع القرار المحدد يتطلب سجلًا مرجعيًا."))

	def previous_status(self):
		before = self.get_doc_before_save()
		return before.status if before else None

	def validate_separation(self):
		if not self.is_new() and self.status in ("Approved", "Rejected"):
			settings = frappe.get_cached_doc("Legal Settings")
			if settings.grievance_decision_separation_required:
				prepared_by = self.prepared_by
				decision_maker = self.decision_maker or frappe.session.user
				if not prepared_by:
					frappe.throw(_("يجب تحديد معد التوصية قبل اعتماد القرار."))
				if prepared_by == decision_maker:
					frappe.throw(
						_("لا يجوز لمعد التوصية اعتماد القرار بنفسه. يجب أن يعتمده مستخدم مخوّل آخر."),
						frappe.PermissionError,
					)

	def validate_status_transition(self):
		if self.is_new():
			return
		old_status = self.previous_status()
		if not old_status or old_status == self.status:
			return
		if old_status in FINAL_STATUSES and not self.flags.decision_correction:
			frappe.throw(_("لا يمكن تعديل قرار بعد اعتماده أو رفضه."))
		if self.flags.decision_internal_approval:
			return
		if not has_any_role({DECISION_ROLE}):
			frappe.throw(
				_("تغيير حالة القرار يتطلب دور المعتمد المخوّل."),
				frappe.PermissionError,
			)
		allowed = {
			"Draft Recommendation": {"Pending Approval", "Rejected"},
			"Pending Approval": {"Approved", "Rejected"},
			"Approved": {"Implemented", "Archived"},
			"Rejected": {"Archived"},
			"Implemented": {"Archived"},
		}
		if self.status not in allowed.get(old_status, set()):
			frappe.throw(_("انتقال حالة القرار غير مسموح."))

	def validate_final_fields(self):
		if self.status in ("Approved", "Rejected"):
			if not self.final_decision:
				frappe.throw(_("النص النهائي للقرار مطلوب قبل الاعتماد أو الرفض."))
			if not self.decision_date:
				self.decision_date = today()
			if not self.decision_maker:
				self.decision_maker = frappe.session.user
			if not self.approved_on:
				self.approved_on = now_datetime()
			if self.status == "Rejected" and not self.rejection_reason:
				frappe.throw(_("سبب الرفض مطلوب عند رفض القرار."))
		if self.status in ("Approved", "Implemented") and not self.decision_maker:
			frappe.throw(_("معتمد القرار مطلوب."))

	def before_save(self):
		if not self.is_new() and self.previous_status() in FINAL_STATUSES:
			if not self.flags.decision_correction:
				blocked = {
					"final_decision",
					"decision_date",
					"decision_maker",
					"approved_on",
					"recommendation",
					"prepared_by",
					"status",
				}
				for fieldname in blocked:
					if self.has_value_changed(fieldname):
						frappe.throw(
							_("القرار المعتمد غير قابل للتعديل. استخدم إجراء تصحيح موثقًا."),
							frappe.PermissionError,
						)
			elif not is_system_admin():
				frappe.throw(_("تصحيح القرار يتطلب مدير النظام القانوني."), frappe.PermissionError)

	def on_trash(self):
		if self.status in FINAL_STATUSES and not is_system_admin():
			frappe.throw(
				_("لا يمكن حذف قرار معتمد إلا من مدير النظام القانوني."),
				frappe.PermissionError,
			)
