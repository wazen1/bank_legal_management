import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import today

from bank_legal_management.utils import (
	is_system_admin,
	notify_users,
	require_roles,
)

APPROVER_ROLES = {"Legal Department Manager", "Authorized Decision Maker"}
OPINION_ROLES = {"Legal Department Manager", "Legal Opinion Officer", "Legal Officer"}
TERMINAL_STATUSES = {"Approved", "Superseded", "Rejected"}


class LegalOpinion(Document):
	def before_insert(self):
		if not self.opinion_request:
			frappe.throw(_("يجب ربط الرأي بطلب رأي قانوني."))
		if self.status not in (None, "", "Draft"):
			frappe.throw(_("يجب إنشاء نسخة الرأي بحالة مسودة."))
		self.status = "Draft"
		self.prepared_by = self.prepared_by or frappe.session.user
		if not self.opinion_title:
			self.opinion_title = frappe.db.get_value(
				"Legal Opinion Request", self.opinion_request, "request_title"
			)
		self.version = self.get_next_version()
		self.is_current = 0

	def get_next_version(self):
		current = frappe.db.sql(
			"SELECT MAX(version) FROM `tabLegal Opinion` WHERE opinion_request = %s",
			(self.opinion_request,),
		)
		next_version = (current[0][0] or 0) + 1 if current else 1
		if self.version and self.version != 1:
			if frappe.db.exists(
				"Legal Opinion",
				{"opinion_request": self.opinion_request, "version": self.version},
			):
				frappe.throw(_("رقم النسخة المحدد موجود بالفعل لهذا الطلب."))
			return self.version
		return next_version

	def validate(self):
		if not self.opinion_text and self.status in ("Under Review", "Approved"):
			frappe.throw(_("نص الرأي القانوني مطلوب."))
		self.validate_status_transition()
		if self.status == "Approved":
			if not self.approved_by:
				self.approved_by = frappe.session.user
			if not self.approval_date:
				self.approval_date = today()
			self.is_current = 1

	def validate_status_transition(self):
		before = self.get_doc_before_save()
		if not before or before.status == self.status:
			return
		if is_system_admin() or self.flags.opinion_internal_update:
			return
		require_roles(OPINION_ROLES | APPROVER_ROLES)
		allowed = {
			"Draft": {"Under Review", "Rejected"},
			"Under Review": {"Draft", "Approved", "Rejected"},
			"Approved": {"Superseded"},
			"Rejected": set(),
			"Superseded": set(),
		}
		if self.status not in allowed.get(before.status, set()):
			frappe.throw(_("انتقال حالة نسخة الرأي غير مسموح."))

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
						frappe.throw(_("نسخة الرأي المعتمدة غير قابلة للتعديل."), frappe.PermissionError)

	@frappe.whitelist()
	def approve_opinion(self):
		self.check_permission("read")
		if self.status not in ("Draft", "Under Review"):
			frappe.throw(_("لا يمكن اعتماد نسخة الرأي في حالتها الحالية."))
		require_roles(APPROVER_ROLES)
		if self.prepared_by == frappe.session.user and not is_system_admin():
			frappe.throw(
				_("لا يجوز لمعد الرأي اعتماده بنفسه."),
				frappe.PermissionError,
			)
		if not self.opinion_text:
			frappe.throw(_("نص الرأي القانوني مطلوب قبل الاعتماد."))
		frappe.db.set_value(
			"Legal Opinion",
			{"opinion_request": self.opinion_request, "name": ("!=", self.name)},
			{"is_current": 0, "status": "Superseded"},
		)
		self.flags.opinion_internal_update = True
		self.status = "Approved"
		self.is_current = 1
		self.approved_by = frappe.session.user
		self.approval_date = today()
		self.save(ignore_permissions=True)
		request = frappe.get_doc("Legal Opinion Request", self.opinion_request)
		request.flags.opinion_status_update = True
		request.final_opinion = self.opinion_text
		request.save(ignore_permissions=True)
		notify_users(
			{request.requested_by},
			self.doctype,
			self.name,
			_("تم اعتماد رأي قانوني"),
		)
		return {"name": self.name, "status": self.status}
