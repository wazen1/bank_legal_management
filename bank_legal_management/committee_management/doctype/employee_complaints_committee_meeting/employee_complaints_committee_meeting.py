import math

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, getdate, get_time, now_datetime, today

from bank_legal_management.utils import (
	get_grievance_queue_users,
	get_settings,
	get_user_for_employee,
	is_system_admin,
	notify_users,
	require_roles,
)

MEETING_ROLES = {
	"Employee Complaints Committee Chair",
	"Employee Complaints Committee Secretary",
	"Legal Department Manager",
}
MINUTES_APPROVAL_ROLES = {
	"Employee Complaints Committee Chair",
	"Legal System Administrator",
}
STATUS_TRANSITIONS = {
	"Draft": {"Scheduled", "Cancelled"},
	"Scheduled": {"Completed", "Cancelled"},
	"Completed": set(),
	"Cancelled": {"Scheduled"},
}


class EmployeeComplaintsCommitteeMeeting(Document):
	def before_insert(self):
		if self.status not in (None, "", "Draft"):
			frappe.throw(_("يجب إنشاء الاجتماع بحالة مسودة."))
		self.status = "Draft"
		self.prepared_by = self.prepared_by or frappe.session.user
		if not self.meeting_date:
			self.meeting_date = today()

	def validate(self):
		if not self.committee:
			frappe.throw(_("يجب تحديد اللجنة."))
		if not frappe.db.exists("Employee Complaints Committee", self.committee):
			frappe.throw(_("اللجنة المحددة غير موجودة."))
		if not self.meeting_date:
			frappe.throw(_("تاريخ الاجتماع مطلوب."))
		if self.from_time and self.to_time:
			if get_time(self.from_time) >= get_time(self.to_time):
				frappe.throw(_("وقت نهاية الاجتماع يجب أن يكون بعد وقت البداية."))
		self.validate_status_transition()
		self.populate_agenda_titles()
		self.validate_duplicate_agenda()
		self.populate_attendees()
		self.compute_quorum()
		if self.status == "Scheduled":
			committee_status = frappe.db.get_value(
				"Employee Complaints Committee", self.committee, "status"
			)
			if committee_status != "Active":
				frappe.throw(_("لا يمكن جدولة اجتماع لجنة غير نشطة."))
		if self.status == "Completed":
			if not self.minutes:
				frappe.throw(_("محضر الاجتماع مطلوب قبل تعيين الاجتماع كمكتمل."))
			if not self.quorum_met:
				frappe.throw(_("لا يمكن إكمال الاجتماع دون تحقق النصاب."))
			if not self.minutes_status:
				self.minutes_status = "Draft"

	def validate_status_transition(self):
		before = self.get_doc_before_save()
		if not before or before.status == self.status:
			return
		if is_system_admin():
			return
		require_roles(MEETING_ROLES | {"Legal System Administrator"})
		if self.status not in STATUS_TRANSITIONS.get(before.status, set()):
			frappe.throw(
				_("انتقال حالة الاجتماع من {0} إلى {1} غير مسموح.").format(
					before.status, self.status
				)
			)
		if before.status == "Completed" and self.status != "Completed":
			frappe.throw(_("لا يمكن إعادة فتح اجتماع مكتمل."))

	def populate_agenda_titles(self):
		for row in self.grievances:
			if not row.grievance:
				frappe.throw(_("يجب تحديد الشكوى في كل بند من بنود جدول الأعمال."))
			if not frappe.db.exists("Employee Legal Grievance", row.grievance):
				frappe.throw(_("الشكوى {0} غير موجودة.").format(row.grievance))
			row.grievance_title = frappe.db.get_value(
				"Employee Legal Grievance", row.grievance, "grievance_title"
			)

	def validate_duplicate_agenda(self):
		seen = set()
		for row in self.grievances:
			if row.grievance in seen:
				frappe.throw(_("لا يمكن تكرار الشكوى نفسها في جدول الأعمال."))
			seen.add(row.grievance)

	def populate_attendees(self):
		if self.attendees and self.status != "Draft":
			return
		committee = frappe.get_doc("Employee Complaints Committee", self.committee)
		employees = []
		if committee.chair:
			employees.append(committee.chair)
		if committee.secretary and committee.secretary not in employees:
			employees.append(committee.secretary)
		for row in committee.members:
			if row.employee and row.employee not in employees and row.active:
				employees.append(row.employee)
		if not employees:
			return
		existing = {row.employee for row in self.attendees if row.employee}
		for employee in employees:
			if employee in existing:
				continue
			values = frappe.db.get_value(
				"Employee",
				employee,
				["employee_name"],
				as_dict=True,
			)
			self.append(
				"attendees",
				{
					"employee": employee,
					"member_name": values.employee_name if values else None,
					"attendance": "Present",
				},
			)

	def compute_quorum(self):
		committee = frappe.get_doc("Employee Complaints Committee", self.committee)
		total_members = len(
			[
				row
				for row in committee.members
				if row.employee
				and row.active
				and (not row.membership_end or getdate(row.membership_end) >= getdate(today()))
			]
		)
		if not total_members:
			total_members = len(self.attendees)
		percent = cint(committee.quorum_percent or get_settings().get("committee_quorum_percent") or 50)
		present = len([row for row in self.attendees if row.attendance == "Present"])
		self.quorum_required = math.ceil(total_members * percent / 100.0) if total_members else 0
		self.quorum_met = 1 if total_members and present >= self.quorum_required else 0

	def on_update(self):
		before = self.get_doc_before_save()
		if not before or before.status == self.status:
			return
		if self.status == "Scheduled":
			self.update_linked_grievances()
		if self.status in ("Scheduled", "Completed"):
			recipients = set()
			for row in self.attendees:
				user = get_user_for_employee(row.employee)
				if user:
					recipients.add(user)
			label = _("تم جدولة اجتماع لجنة") if self.status == "Scheduled" else _("تم إكمال اجتماع لجنة")
			notify_users(recipients, self.doctype, self.name, label)

	def update_linked_grievances(self):
		for row in self.grievances:
			if not row.grievance:
				continue
			from bank_legal_management.utils import is_user_enabled

			grievance = frappe.get_doc("Employee Legal Grievance", row.grievance)
			if grievance.status in ("Decision Issued", "Closed", "Rejected"):
				continue
			grievance.flags.grievance_controlled_update = True
			grievance.last_committee_meeting = self.name
			previous_status = grievance.status
			if grievance.status in ("Committee Review", "Committee Recommendation"):
				grievance.status = "Scheduled for Meeting"
			grievance.save(ignore_permissions=True)
			log = frappe.get_doc(
				{
					"doctype": "Grievance Action Log",
					"grievance": grievance.name,
					"action": "Schedule Meeting",
					"previous_status": previous_status,
					"new_status": grievance.status,
					"responsible_party": _("لجنة شكاوى الموظفين"),
					"performed_by": frappe.session.user,
					"action_time": now_datetime(),
					"notes": _("تمت جدولة الاجتماع {0}.").format(self.name),
					"is_system_generated": 1,
				}
			)
			log.insert(ignore_permissions=True)
			notify_users(
				get_grievance_queue_users(grievance),
				grievance.doctype,
				grievance.name,
				_("تمت جدولة اجتماع للشكوى"),
			)

	@frappe.whitelist()
	def approve_minutes(self):
		self.check_permission("read")
		if self.status != "Completed":
			frappe.throw(_("لا يمكن اعتماد محضر اجتماع غير مكتمل."))
		if self.minutes_status == "Approved":
			frappe.throw(_("محضر الاجتماع معتمد مسبقًا."))
		require_roles(MINUTES_APPROVAL_ROLES)
		if not self.minutes:
			frappe.throw(_("محضر الاجتماع مطلوب قبل الاعتماد."))
		if self.prepared_by == frappe.session.user and not is_system_admin():
			frappe.throw(
				_("لا يجوز لمعد المحضر اعتماده بنفسه إلا من مدير النظام."),
				frappe.PermissionError,
			)
		self.flags.meeting_internal_update = True
		self.minutes_status = "Approved"
		self.approved_by = frappe.session.user
		self.approved_on = now_datetime()
		self.save(ignore_permissions=True)
		return {"name": self.name, "minutes_status": self.minutes_status}

	def on_trash(self):
		if self.status not in ("Draft", "Cancelled") and not is_system_admin():
			frappe.throw(_("لا يمكن حذف اجتماع منعقد."), frappe.PermissionError)
