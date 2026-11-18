import frappe

from bank_legal_management.utils import get_grievance_employee_user


def _get_grievance(name):
	doc = frappe.get_doc("Employee Legal Grievance", name)
	doc.check_permission("read")
	return doc


@frappe.whitelist()
def get_available_grievance_actions(name):
	return _get_grievance(name).get_available_grievance_actions()


@frappe.whitelist(methods=["POST"])
def apply_grievance_action(name, action, notes=None, recommendation=None, committee=None):
	doc = _get_grievance(name)
	return doc.apply_grievance_action(
		action=action,
		notes=notes,
		recommendation=recommendation,
		committee=committee,
	)


@frappe.whitelist(methods=["POST"])
def provide_grievance_information(name, response_text, attachment=None):
	doc = _get_grievance(name)
	return doc.provide_information(response_text=response_text, attachment=attachment)


@frappe.whitelist(methods=["POST"])
def transfer_grievance_jurisdiction(name, new_jurisdiction, reason):
	doc = _get_grievance(name)
	return doc.transfer_jurisdiction(new_jurisdiction=new_jurisdiction, reason=reason)


@frappe.whitelist(methods=["POST"])
def issue_grievance_decision(name, decision_text, external_reference=None):
	doc = _get_grievance(name)
	return doc.issue_decision(decision_text=decision_text, external_reference=external_reference)


@frappe.whitelist()
def get_grievance_timeline(name):
	doc = _get_grievance(name)
	logs = frappe.get_list(
		"Grievance Action Log",
		filters={"grievance": name},
		fields=[
			"name",
			"action",
			"previous_status",
			"new_status",
			"responsible_party",
			"performed_by",
			"action_time",
			"notes",
			"request_reason",
			"transfer_reason",
			"original_jurisdiction",
			"new_jurisdiction",
		],
		order_by="action_time asc, creation asc",
	)
	clarifications = []
	for row in doc.clarifications:
		clarifications.append(
			{
				"requested_on": row.requested_on,
				"request_text": row.request_text,
				"response_text": row.response_text,
				"responded_on": row.responded_on,
				"status": row.status,
			}
		)
	return {
		"name": doc.name,
		"status": doc.status,
		"employee_name": doc.employee_name,
		"actions": logs,
		"clarifications": clarifications,
	}


@frappe.whitelist(methods=["POST"])
def approve_committee_minutes(name):
	doc = frappe.get_doc("Employee Complaints Committee Meeting", name)
	doc.check_permission("read")
	return doc.approve_minutes()


@frappe.whitelist(methods=["POST"])
def submit_expense_for_review(name):
	doc = frappe.get_doc("Legal Expense", name)
	doc.check_permission("read")
	return doc.submit_for_review()


@frappe.whitelist(methods=["POST"])
def approve_legal_expense(name):
	doc = frappe.get_doc("Legal Expense", name)
	doc.check_permission("read")
	return doc.approve_expense()


@frappe.whitelist(methods=["POST"])
def reject_legal_expense(name, rejection_reason):
	doc = frappe.get_doc("Legal Expense", name)
	doc.check_permission("read")
	return doc.reject_expense(rejection_reason=rejection_reason)


@frappe.whitelist(methods=["POST"])
def mark_legal_expense_paid(name):
	doc = frappe.get_doc("Legal Expense", name)
	doc.check_permission("read")
	return doc.mark_paid()


@frappe.whitelist(methods=["POST"])
def cancel_legal_expense(name):
	doc = frappe.get_doc("Legal Expense", name)
	doc.check_permission("read")
	return doc.cancel_expense()


@frappe.whitelist(methods=["POST"])
def request_opinion_clarification(name, clarification_request):
	doc = frappe.get_doc("Legal Opinion Request", name)
	doc.check_permission("read")
	return doc.request_clarification(clarification_request=clarification_request)


@frappe.whitelist(methods=["POST"])
def provide_opinion_clarification(name, clarification_response):
	doc = frappe.get_doc("Legal Opinion Request", name)
	doc.check_permission("read")
	return doc.provide_clarification(clarification_response=clarification_response)


@frappe.whitelist(methods=["POST"])
def approve_legal_opinion(name):
	doc = frappe.get_doc("Legal Opinion", name)
	doc.check_permission("read")
	return doc.approve_opinion()


@frappe.whitelist()
def get_current_employee():
	from bank_legal_management.utils import get_employee_for_user, get_employee_snapshot

	employee = get_employee_for_user()
	if not employee:
		return None
	snapshot = get_employee_snapshot(employee)
	snapshot.update({"name": employee, "user": get_grievance_employee_user(frappe._dict({"employee": employee}))})
	return snapshot
