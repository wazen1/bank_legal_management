import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, today

from bank_legal_management.utils import get_settings, is_system_admin, require_roles

COMMITTEE_ROLES = {
	"Employee Complaints Committee Chair",
	"Employee Complaints Committee Secretary",
	"Legal Department Manager",
}
STATUS_TRANSITIONS = {
	"Draft": {"Active", "Inactive"},
	"Active": {"Inactive", "Expired"},
	"Inactive": {"Active", "Expired"},
	"Expired": {"Inactive"},
}


class EmployeeComplaintsCommittee(Document):
	def before_insert(self):
		if self.status not in (None, "", "Draft"):
			frappe.throw(_("يجب إنشاء اللجنة بحالة مسودة."))
		self.status = "Draft"
		if not self.quorum_percent:
			self.quorum_percent = get_settings().get("committee_quorum_percent") or 50

	def validate(self):
		if not self.committee_name:
			frappe.throw(_("اسم اللجنة مطلوب."))
		self.validate_dates()
		self.validate_members()
		self.validate_status_transition()
		self.validate_active_requirements()
		if self.quorum_percent is not None and not 1 <= self.quorum_percent <= 100:
			frappe.throw(_("نسبة النصاب يجب أن تكون بين 1 و100."))

	def validate_dates(self):
		if self.start_date and self.end_date:
			if getdate(self.start_date) > getdate(self.end_date):
				frappe.throw(_("تاريخ بداية اللجنة يجب أن يسبق تاريخ نهايتها."))
		if self.formation_date and self.start_date:
			if getdate(self.formation_date) > getdate(self.start_date):
				frappe.throw(_("تاريخ التشكيل لا يمكن أن يتجاوز تاريخ بداية العمل."))

	def validate_members(self):
		seen = set()
		for row in self.members:
			if not row.employee:
				frappe.throw(_("يجب تحديد الموظف في كل صف من أعضاء اللجنة."))
			if row.employee in seen:
				frappe.throw(_("لا يمكن تكرار الموظف {0} في عضوية اللجنة.").format(row.employee))
			seen.add(row.employee)
			employee = frappe.db.get_value(
				"Employee",
				row.employee,
				["employee_name", "designation"],
				as_dict=True,
			)
			if not employee:
				frappe.throw(_("سجل الموظف {0} غير موجود.").format(row.employee))
			row.member_name = employee.employee_name
			row.designation = employee.designation
			if row.membership_end and getdate(row.membership_end) < getdate(today()):
				row.active = 0
			elif row.active is None:
				row.active = 1

	def validate_status_transition(self):
		before = self.get_doc_before_save()
		if not before or before.status == self.status:
			return
		if is_system_admin():
			return
		require_roles(COMMITTEE_ROLES | {"Legal System Administrator"})
		if self.status not in STATUS_TRANSITIONS.get(before.status, set()):
			frappe.throw(
				_("انتقال حالة اللجنة من {0} إلى {1} غير مسموح.").format(
					before.status, self.status
				)
			)

	def validate_active_requirements(self):
		if self.status == "Active":
			if not self.chair:
				frappe.throw(_("يجب تحديد رئيس اللجنة قبل تفعيلها."))
			if not self.secretary:
				frappe.throw(_("يجب تحديد أمين اللجنة قبل تفعيلها."))
			if self.chair == self.secretary:
				frappe.throw(_("لا يمكن أن يكون الرئيس وأمين اللجنة نفس الشخص."))
			if not self.start_date:
				self.start_date = today()
			if not self.members:
				frappe.throw(_("يجب إضافة أعضاء اللجنة قبل تفعيلها."))

	def on_trash(self):
		references = (
			frappe.db.exists("Employee Legal Grievance", {"committee": self.name})
			or frappe.db.exists("Employee Complaints Committee Meeting", {"committee": self.name})
		)
		if references and not is_system_admin():
			frappe.throw(_("لا يمكن حذف لجنة مرتبطة بشكاوى أو اجتماعات."), frappe.PermissionError)

	@frappe.whitelist()
	def get_active_members(self):
		self.check_permission("read")
		return [
			row.employee
			for row in self.members
			if row.active and (not row.membership_end or getdate(row.membership_end) >= getdate(today()))
		]
