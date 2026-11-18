import json

import frappe
from frappe import _
from frappe.utils import add_days, getdate, now_datetime, today

from bank_legal_management.utils import (
	get_grievance_queue_users,
	get_settings,
	get_user_for_employee,
	is_user_enabled,
	notify_users,
)


def process_legal_deadlines():
	settings = get_settings()
	if not settings.get("enable_scheduler_alerts"):
		return
	enqueue_alerts_for_hearings(settings)
	enqueue_alerts_for_contracts(settings)
	enqueue_alerts_for_obligations(settings)
	enqueue_alerts_for_opinions(settings)
	enqueue_alerts_for_meetings(settings)
	enqueue_alerts_for_stale_grievances(settings)


def enqueue_alerts_for_hearings(settings):
	days = int(settings.get("hearing_alert_days") or 3)
	until = add_days(today(), days)
	rows = frappe.get_all(
		"Legal Hearing",
		filters={
			"status": "Scheduled",
			"hearing_date": ("between", [today(), until]),
		},
		fields=["name", "legal_case", "hearing_date"],
	)
	for row in rows:
		recipients = get_alert_recipients("Cases")
		recipients.update(get_case_recipients(row.legal_case))
		create_alert(
			alert_type="Hearing Reminder",
			reference_doctype="Legal Hearing",
			reference_name=row.name,
			alert_key=f"hearing:{row.name}:{row.hearing_date}",
			recipients=recipients,
			details=_("جلسة قانونية قادمة بتاريخ {0}.").format(row.hearing_date),
		)


def get_case_recipients(case_name):
	recipients = set()
	if not case_name:
		return recipients
	assigned_officer = frappe.db.get_value("Legal Case", case_name, "assigned_officer")
	if assigned_officer:
		user = get_user_for_employee(assigned_officer)
		if user:
			recipients.add(user)
	return recipients


def enqueue_alerts_for_contracts(settings):
	days = int(settings.get("contract_expiry_alert_days") or 30)
	until = add_days(today(), days)
	rows = frappe.get_all(
		"Legal Contract",
		filters={
			"status": ("in", ["Active", "Expiring"]),
			"end_date": ("is", "set"),
		},
		fields=["name", "end_date", "contract_owner", "status"],
	)
	for row in rows:
		end_date = getdate(row.end_date)
		recipients = get_alert_recipients("Contracts")
		if row.contract_owner:
			user = get_user_for_employee(row.contract_owner)
			if user:
				recipients.add(user)
		if end_date < getdate(today()):
			update_contract_status(row.name, "Expired")
			create_alert(
				alert_type="Contract Expired",
				reference_doctype="Legal Contract",
				reference_name=row.name,
				alert_key=f"contract-expired:{row.name}:{row.end_date}",
				recipients=recipients,
				details=_("انتهت مدة العقد بتاريخ {0}.").format(row.end_date),
			)
		elif end_date <= getdate(until):
			update_contract_status(row.name, "Expiring")
			create_alert(
				alert_type="Contract Expiry Reminder",
				reference_doctype="Legal Contract",
				reference_name=row.name,
				alert_key=f"contract-expiry:{row.name}:{row.end_date}",
				recipients=recipients,
				details=_("يقترب انتهاء العقد بتاريخ {0}.").format(row.end_date),
			)


def update_contract_status(contract, status):
	if frappe.db.get_value("Legal Contract", contract, "status") == status:
		return
	doc = frappe.get_doc("Legal Contract", contract)
	if doc.status in ("Terminated", "Archived", "Renewed", "Expired"):
		return
	doc.flags.system_status_update = True
	doc.status = status
	doc.save(ignore_permissions=True)


def enqueue_alerts_for_obligations(settings):
	days = int(settings.get("obligation_due_alert_days") or 7)
	until = add_days(today(), days)
	rows = frappe.get_all(
		"Contract Obligation",
		filters={
			"status": ("in", ["Pending", "In Progress"]),
			"next_due_date": ("between", [today(), until]),
		},
		fields=["name", "contract", "next_due_date", "follow_up_owner"],
	)
	for row in rows:
		recipients = get_alert_recipients("Contracts")
		if row.follow_up_owner:
			user = get_user_for_employee(row.follow_up_owner)
			if user:
				recipients.add(user)
		create_alert(
			alert_type="Obligation Due Reminder",
			reference_doctype="Contract Obligation",
			reference_name=row.name,
			alert_key=f"obligation:{row.name}:{row.next_due_date}",
			recipients=recipients,
			details=_("التزام تعاقدي مستحق بتاريخ {0}.").format(row.next_due_date),
		)


def enqueue_alerts_for_opinions(settings):
	days = int(settings.get("opinion_due_alert_days") or 3)
	until = add_days(today(), days)
	rows = frappe.get_all(
		"Legal Opinion Request",
		filters={
			"status": ("not in", ["Approved", "Rejected", "Closed", "Cancelled"]),
			"due_date": ("between", [today(), until]),
		},
		fields=["name", "due_date", "requested_by", "assigned_officer"],
	)
	for row in rows:
		recipients = get_alert_recipients("Opinions")
		if row.requested_by:
			recipients.add(row.requested_by)
		if row.assigned_officer:
			user = get_user_for_employee(row.assigned_officer)
			if user:
				recipients.add(user)
		create_alert(
			alert_type="Legal Opinion Due Reminder",
			reference_doctype="Legal Opinion Request",
			reference_name=row.name,
			alert_key=f"opinion:{row.name}:{row.due_date}",
			recipients=recipients,
			details=_("طلب رأي قانوني مستحق بتاريخ {0}.").format(row.due_date),
		)


def enqueue_alerts_for_meetings(settings):
	days = int(settings.get("meeting_alert_days") or 2)
	until = add_days(today(), days)
	rows = frappe.get_all(
		"Employee Complaints Committee Meeting",
		filters={
			"status": "Scheduled",
			"meeting_date": ("between", [today(), until]),
		},
		fields=["name", "meeting_date", "committee"],
	)
	for row in rows:
		recipients = get_alert_recipients("Committee")
		create_alert(
			alert_type="Committee Meeting Reminder",
			reference_doctype="Employee Complaints Committee Meeting",
			reference_name=row.name,
			alert_key=f"meeting:{row.name}:{row.meeting_date}",
			recipients=recipients,
			details=_("اجتماع لجنة شكاوى الموظفين بتاريخ {0}.").format(row.meeting_date),
		)


def enqueue_alerts_for_stale_grievances(settings):
	days = int(settings.get("grievance_stale_days") or 14)
	cutoff = add_days(today(), -days)
	rows = frappe.get_all(
		"Employee Legal Grievance",
		filters={
			"docstatus": 1,
			"status": ("not in", ["Decision Issued", "Closed", "Rejected"]),
			"modified": ("<", cutoff),
		},
		fields=["name", "jurisdiction_type", "committee", "status", "modified"],
	)
	for row in rows:
		grievance = frappe.get_doc("Employee Legal Grievance", row.name)
		recipients = get_grievance_queue_users(grievance)
		create_alert(
			alert_type="Stale Grievance Reminder",
			reference_doctype="Employee Legal Grievance",
			reference_name=row.name,
			alert_key=f"grievance-stale:{row.name}:{getdate(row.modified)}",
			recipients=recipients,
			details=_("شكوى قيد المعالجة منذ فترة تتجاوز المدة المحددة."),
			repeat_after_days=days,
		)


def get_alert_recipients(scope):
	settings = get_settings()
	recipients = set()
	for row in settings.get("alert_recipients") or []:
		if row.enabled and row.user and row.alert_scope in ("All", scope):
			recipients.add(row.user)
	return recipients


def create_alert(
	alert_type,
	reference_doctype,
	reference_name,
	alert_key,
	recipients,
	details=None,
	repeat_after_days=None,
):
	filters = {"alert_key": alert_key}
	if repeat_after_days:
		filters = {
			"alert_type": alert_type,
			"reference_name": reference_name,
			"creation": (">", add_days(now_datetime(), -int(repeat_after_days))),
		}
	if frappe.db.exists("Legal Reminder Log", filters):
		return
	recipients = {user for user in recipients if is_user_enabled(user)}
	if not recipients:
		return
	log = frappe.get_doc(
		{
			"doctype": "Legal Reminder Log",
			"alert_type": alert_type,
			"alert_key": alert_key,
			"reference_doctype": reference_doctype,
			"reference_name": reference_name,
			"recipients": json.dumps(sorted(recipients), ensure_ascii=False),
			"status": "Queued",
			"details": details,
		}
	)
	log.insert(ignore_permissions=True)
	try:
		notified = notify_users(
			recipients,
			reference_doctype,
			reference_name,
			_("تنبيه قانوني"),
		)
		log.status = "Sent" if notified else "Skipped"
		log.sent_on = now_datetime()
	except Exception:
		log.status = "Failed"
		log.error_message = frappe.get_traceback()[:1000]
		frappe.log_error(title="Legal reminder failed", message=frappe.get_traceback())
	log.save(ignore_permissions=True)
