import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime, today

from bank_legal_management.utils import (
	get_employee_for_user,
	get_settings,
	has_any_role,
	is_system_admin,
	notify_status_change,
	notify_users,
	require_roles,
)

LEGAL_OPINION_ROLES = {
	"Legal Department Manager",
	"Legal Opinion Officer",
	"Legal Officer",
}
MANAGER_ROLES = {"Legal Department Manager", "Legal System Administrator"}
REQUESTER_ROLE = "Legal Opinion Requester"
DECISION_ROLE = "Authorized Decision Maker"
TERMINAL_STATUSES = {"Approved", "Rejected", "Closed", "Cancelled"}
STATUS_TRANSITIONS = {
	"Draft": {"Submitted", "Cancelled"},
	"Submitted": {"Under Review", "Rejected"},
	"Under Review": {"Awaiting Clarification", "Draft Opinion", "Pending Approval"},
	"Awaiting Clarification": {"Under Review"},
	"Draft Opinion": {"Legal Review"},
	"Legal Review": {"Draft Opinion", "Pending Approval"},
	"Pending Approval": {"Approved", "Rejected"},
	"Approved": {"Closed"},
	"Rejected": {"Closed"},
	"Closed": set(),
	"Cancelled": set(),
}
TRANSITION_ROLES = {
	"Draft": {REQUESTER_ROLE} | LEGAL_OPINION_ROLES | MANAGER_ROLES,
	"Submitted": LEGAL_OPINION_ROLES | MANAGER_ROLES | {DECISION_ROLE},
	"Under Review": LEGAL_OPINION_ROLES | MANAGER_ROLES,
	"Awaiting Clarification": LEGAL_OPINION_ROLES | MANAGER_ROLES | {REQUESTER_ROLE},
	"Draft Opinion": LEGAL_OPINION_ROLES | MANAGER_ROLES,
	"Legal Review": LEGAL_OPINION_ROLES | MANAGER_ROLES,
	"Pending Approval": {DECISION_ROLE} | MANAGER_ROLES,
	"Approved": LEGAL_OPINION_ROLES | MANAGER_ROLES,
	"Rejected": LEGAL_OPINION_ROLES | MANAGER_ROLES,
}


class LegalOpinionRequest(Document):
	def before_insert(self):
		if self.status not in (None, "", "Draft"):
			frappe.throw(_("يجب إنشاء طلب الرأي بحالة مسودة."))
		self.status = "Draft"
		self.set_requester()
		if not self.request_date:
			self.request_date = today()

	def set_requester(self):
		own_employee = get_employee_for_user()
		if not self.requested_by:
			self.requested_by = frappe.session.user
		if self.requested_by != frappe.session.user:
			settings = get_settings()
			allowed = has_any_role(LEGAL_OPINION_ROLES | MANAGER_ROLES) and settings.get(
				"allow_opinion_on_behalf"
			)
			if not (allowed or is_system_admin()):
				frappe.throw(
					_("لا يمكنك إنشاء طلب رأي باسم مستخدم آخر."),
					frappe.PermissionError,
				)
		if not self.requesting_employee and own_employee and self.requested_by == frappe.session.user:
			self.requesting_employee = own_employee
		elif self.requesting_employee:
			employee_user = frappe.db.get_value(
				"Employee", self.requesting_employee, "user_id"
			)
			if not is_system_admin() and employee_user and employee_user != self.requested_by:
				frappe.throw(_("الموظف الطالب لا يطابق المستخدم الطالب."))

	def validate(self):
		self.validate_requester_readonly()
		before = self.get_doc_before_save()
		self.validate_transition(before)
		self.validate_required_content()
		self.set_approval_fields()

	def on_update(self):
		before = self.get_doc_before_save()
		if before and before.status != self.status:
			notify_status_change(
				self,
				users={self.requested_by} if self.requested_by else set(),
				subject=_("تحديث طلب رأي قانوني"),
			)

	def validate_requester_readonly(self):
		if self.is_new() or is_system_admin() or self.flags.opinion_status_update:
			return
		roles = set(frappe.get_roles())
		if roles.intersection(LEGAL_OPINION_ROLES | MANAGER_ROLES):
			return
		before = self.get_doc_before_save()
		if not before:
			return
		if before.status != "Draft":
			for df in self.meta.fields:
				if df.fieldtype in ("Section Break", "Column Break", "Tab Break"):
					continue
				if df.fieldname in ("status",):
					continue
				if df.fieldname and self.has_value_changed(df.fieldname):
					frappe.throw(
						_("لا يمكن تعديل طلب الرأي بعد تقديمه. استخدم طلب التوضيح."),
						frappe.PermissionError,
					)

	def validate_transition(self, before):
		if not before or before.status == self.status:
			return
		if is_system_admin():
			return
		roles = set(frappe.get_roles())
		if not roles.intersection(TRANSITION_ROLES.get(before.status, set())):
			frappe.throw(
				_("ليست لديك صلاحية تنفيذ انتقال حالة طلب الرأي."),
				frappe.PermissionError,
			)
		allowed = STATUS_TRANSITIONS.get(before.status, set())
		if self.status not in allowed:
			frappe.throw(
				_("انتقال حالة طلب الرأي من {0} إلى {1} غير مسموح.").format(
					before.status, self.status
				)
			)
		if before.status == "Pending Approval" and self.status == "Approved":
			if DECISION_ROLE not in roles:
				frappe.throw(
					_("اعتماد الرأي القانوني يتطلب دور المعتمد المخوّل."),
					frappe.PermissionError,
				)

	def validate_required_content(self):
		if self.status in ("Submitted", "Under Review", "Draft Opinion", "Pending Approval", "Approved"):
			for fieldname in ("request_title", "subject", "facts", "questions"):
				if not self.get(fieldname):
					frappe.throw(
						_("الحقل {0} مطلوب قبل تقديم الطلب أو معالجته.").format(
							_(self.meta.get_label(fieldname))
						)
					)
		if self.status in ("Draft Opinion", "Pending Approval", "Approved"):
			if not self.final_opinion:
				frappe.throw(_("نص الرأي القانوني مطلوب."))
		if self.status == "Approved":
			if not self.final_opinion:
				frappe.throw(_("لا يمكن اعتماد طلب دون رأي قانوني نهائي."))

	def set_approval_fields(self):
		if self.status == "Approved":
			self.approved_by = self.approved_by or frappe.session.user
			self.approval_date = self.approval_date or today()
		if self.due_date and self.request_date:
			if self.due_date < self.request_date:
				frappe.throw(_("تاريخ الاستحقاق لا يمكن أن يسبق تاريخ الطلب."))

	def before_save(self):
		before = self.get_doc_before_save()
		if before and before.status in TERMINAL_STATUSES and before.status == self.status:
			if not is_system_admin() and not self.flags.opinion_status_update:
				for df in self.meta.fields:
					if df.fieldtype in ("Section Break", "Column Break", "Tab Break"):
						continue
					if df.fieldname == "status":
						continue
					if df.fieldname and self.has_value_changed(df.fieldname):
						frappe.throw(_("طلب الرأي المغلق غير قابل للتعديل."), frappe.PermissionError)

	@frappe.whitelist()
	def request_clarification(self, clarification_request):
		self.check_permission("read")
		if self.status != "Under Review":
			frappe.throw(_("لا يمكن طلب توضيح في الحالة الحالية."))
		require_roles(LEGAL_OPINION_ROLES)
		clarification_request = (clarification_request or "").strip()
		if not clarification_request:
			frappe.throw(_("نص طلب التوضيح مطلوب."))
		self.flags.opinion_status_update = True
		self.clarification_request = clarification_request
		self.clarification_requested_on = now_datetime()
		self.clarification_response = None
		self.clarification_responded_on = None
		self.status = "Awaiting Clarification"
		self.save(ignore_permissions=True)
		return {"name": self.name, "status": self.status}

	@frappe.whitelist()
	def provide_clarification(self, clarification_response):
		self.check_permission("read")
		if self.status != "Awaiting Clarification":
			frappe.throw(_("لا يوجد طلب توضيح مفتوح."))
		if not is_system_admin() and self.requested_by != frappe.session.user:
			user = None
			if self.requesting_employee:
				user = frappe.db.get_value("Employee", self.requesting_employee, "user_id")
			if user != frappe.session.user:
				frappe.throw(
					_("تقديم التوضيح متاح للمستخدم الطالب فقط."),
					frappe.PermissionError,
				)
		clarification_response = (clarification_response or "").strip()
		if not clarification_response:
			frappe.throw(_("نص التوضيح مطلوب."))
		self.flags.opinion_status_update = True
		self.clarification_response = clarification_response
		self.clarification_responded_on = now_datetime()
		self.status = "Under Review"
		self.save(ignore_permissions=True)
		notify_users(
			{self.requested_by},
			self.doctype,
			self.name,
			_("تم استلام توضيح على طلب رأي"),
		)
		return {"name": self.name, "status": self.status}

	@frappe.whitelist()
	def get_opinion_request_timeline(self):
		self.check_permission("read")
		versions = []
		if frappe.db.exists("DocType", "Legal Opinion"):
			versions = frappe.get_all(
				"Legal Opinion",
				filters={"opinion_request": self.name},
				fields=["name", "version", "status", "is_current", "creation"],
				order_by="version desc",
			)
		return {"versions": versions}


def check_request_permission(doc, ptype="read", user=None):
	from bank_legal_management.permissions import legal_opinion_request_has_permission

	return legal_opinion_request_has_permission(doc, ptype, user)
