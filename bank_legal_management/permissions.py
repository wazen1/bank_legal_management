import frappe

from bank_legal_management.utils import (
	GRIEVANCE_PATH_COMMITTEE,
	GRIEVANCE_PATH_LEGAL,
	get_employee_for_user,
)

PRIVILEGED = {"Legal System Administrator"}
AUDIT_ROLES = {"Legal Auditor"}
LEGAL_GRIEVANCE_ROLES = {
	"Legal Department Manager",
	"Legal Grievance Manager",
	"Legal Grievance Officer",
}
COMMITTEE_GRIEVANCE_ROLES = {
	"Employee Complaints Committee Chair",
	"Employee Complaints Committee Secretary",
	"Employee Complaints Committee Member",
}
COMMITTEE_WRITE_ROLES = {
	"Employee Complaints Committee Chair",
	"Employee Complaints Committee Secretary",
}
DECISION_ROLE = "Authorized Decision Maker"
SUBMITTER_ROLE = "Employee Grievance Submitter"
OWN_READ_TYPES = {"read", "select", "report", "export", "print", "email", "share"}


def _roles(user=None):
	return set(frappe.get_roles(user or frappe.session.user))


def _is_privileged(user=None):
	user = user or frappe.session.user
	return user == "Administrator" or bool(PRIVILEGED.intersection(_roles(user)))


def employee_is_owner(doc, user=None):
	user = user or frappe.session.user
	employee = get_employee_for_user(user)
	return bool(
		(employee and doc.get("employee") == employee)
		or (doc.get("raised_by_user") and doc.get("raised_by_user") == user)
	)


def grievance_scope_sql(user=None, table="`tabEmployee Legal Grievance`"):
	"""Return a SQL scope for grievances. None means unrestricted."""
	user = user or frappe.session.user
	if user == "Administrator" or PRIVILEGED.intersection(_roles(user)) or AUDIT_ROLES.intersection(_roles(user)):
		return None

	roles = _roles(user)
	clauses = []
	employee = get_employee_for_user(user)
	if employee:
		clauses.append(f"{table}.`employee` = {frappe.db.escape(employee)}")
	if user:
		clauses.append(f"{table}.`raised_by_user` = {frappe.db.escape(user)}")
	if roles.intersection(LEGAL_GRIEVANCE_ROLES):
		clauses.append(
			f"({table}.`jurisdiction_type` = {frappe.db.escape(GRIEVANCE_PATH_LEGAL)} "
			f"AND {table}.`docstatus` = 1)"
		)
	if roles.intersection(COMMITTEE_GRIEVANCE_ROLES):
		clauses.append(
			f"({table}.`jurisdiction_type` = {frappe.db.escape(GRIEVANCE_PATH_COMMITTEE)} "
			f"AND {table}.`docstatus` = 1)"
		)
	if DECISION_ROLE in roles:
		clauses.append(
			f"{table}.`status` IN ('Pending Decision', 'Decision Issued')"
		)
	if not clauses:
		return "1=0"
	return "(" + " OR ".join(f"({clause})" for clause in clauses) + ")"


def employee_grievance_query(user=None):
	condition = grievance_scope_sql(user)
	return condition or ""


def grievance_has_permission(doc=None, ptype=None, user=None, **kwargs):
	user = user or frappe.session.user
	if not doc:
		return True
	if user == "Administrator":
		return True
	ptype = ptype or "read"
	roles = _roles(user)

	if PRIVILEGED.intersection(roles):
		return True
	if AUDIT_ROLES.intersection(roles):
		return ptype in OWN_READ_TYPES
	if ptype in ("create",):
		return True

	is_submitter_owner = employee_is_owner(doc, user)
	if is_submitter_owner:
		if ptype in OWN_READ_TYPES:
			return True
		if ptype in ("write", "submit"):
			stored_docstatus = 0
			if doc.get("name"):
				stored_docstatus = (
					frappe.db.get_value("Employee Legal Grievance", doc.name, "docstatus") or 0
				)
			return stored_docstatus == 0
		return False

	if ptype in ("write", "submit", "cancel", "delete", "create", "amend"):
		allowed = False
	else:
		allowed = ptype in OWN_READ_TYPES
	if not allowed:
		return False

	if (
		roles.intersection(LEGAL_GRIEVANCE_ROLES)
		and doc.get("jurisdiction_type") == GRIEVANCE_PATH_LEGAL
		and doc.docstatus == 1
	):
		return True
	if (
		roles.intersection(COMMITTEE_GRIEVANCE_ROLES)
		and doc.get("jurisdiction_type") == GRIEVANCE_PATH_COMMITTEE
		and doc.docstatus == 1
	):
		if ptype in ("write", "submit", "cancel", "delete", "amend"):
			return bool(roles.intersection(COMMITTEE_WRITE_ROLES))
		return True
	if DECISION_ROLE in roles and doc.get("status") in (
		"Pending Decision",
		"Decision Issued",
	):
		return ptype in OWN_READ_TYPES
	return False


def grievance_action_log_query(user=None):
	condition = grievance_scope_sql(user, table="g")
	if condition is None:
		return ""
	return (
		"EXISTS (SELECT 1 FROM `tabEmployee Legal Grievance` g "
		"WHERE g.name = `tabGrievance Action Log`.`grievance` "
		f"AND {condition})"
	)


def grievance_action_log_has_permission(doc=None, ptype=None, user=None, **kwargs):
	if not doc:
		return True
	if ptype not in OWN_READ_TYPES:
		return False
	grievance = doc.get("grievance")
	if not grievance:
		return False
	try:
		parent = frappe.get_doc("Employee Legal Grievance", grievance)
	except frappe.DoesNotExistError:
		return False
	return grievance_has_permission(parent, "read", user)


def _opinion_request_sql(user=None, table="`tabLegal Opinion Request`"):
	user = user or frappe.session.user
	if user == "Administrator" or PRIVILEGED.intersection(_roles(user)):
		return None
	roles = _roles(user)
	if {
		"Legal Department Manager",
		"Legal Opinion Officer",
		"Legal Officer",
	}.intersection(roles):
		return None
	if AUDIT_ROLES.intersection(roles):
		return None
	clauses = []
	if "Legal Opinion Requester" in roles:
		clauses.append(f"{table}.`requested_by` = {frappe.db.escape(user)}")
	if DECISION_ROLE in roles:
		clauses.append(f"{table}.`status` IN ('Pending Approval', 'Approved', 'Rejected')")
	if not clauses:
		return "1=0"
	return "(" + " OR ".join(f"({clause})" for clause in clauses) + ")"


def legal_opinion_request_query(user=None):
	return _opinion_request_sql(user) or ""


def legal_opinion_request_has_permission(doc=None, ptype=None, user=None, **kwargs):
	if not doc:
		return True
	user = user or frappe.session.user
	if user == "Administrator" or PRIVILEGED.intersection(_roles(user)):
		return True
	if ptype in ("create",):
		return True
	roles = _roles(user)
	if {"Legal Department Manager", "Legal Opinion Officer", "Legal Officer"}.intersection(roles):
		return True
	if AUDIT_ROLES.intersection(roles):
		return ptype in OWN_READ_TYPES
	if "Legal Opinion Requester" in roles and doc.get("requested_by") == user:
		if ptype in OWN_READ_TYPES:
			return True
		if ptype in ("write", "submit"):
			stored_status = None
			if doc.get("name"):
				stored_status = frappe.db.get_value("Legal Opinion Request", doc.name, "status")
			stored_status = stored_status or doc.get("status")
			return stored_status == "Draft"
		return False
	if DECISION_ROLE in roles and doc.get("status") in (
		"Pending Approval",
		"Approved",
		"Rejected",
	):
		if ptype in OWN_READ_TYPES:
			return True
		if ptype in ("write", "submit"):
			stored_status = None
			if doc.get("name"):
				stored_status = frappe.db.get_value("Legal Opinion Request", doc.name, "status")
			stored_status = stored_status or doc.get("status")
			return stored_status == "Pending Approval" and doc.get("status") in (
				"Approved",
				"Rejected",
			)
		return False
	return False


def legal_opinion_query(user=None):
	user = user or frappe.session.user
	if user == "Administrator" or PRIVILEGED.intersection(_roles(user)):
		return ""
	roles = _roles(user)
	if {
		"Legal Department Manager",
		"Legal Opinion Officer",
		"Legal Officer",
		"Authorized Decision Maker",
	}.intersection(roles) or AUDIT_ROLES.intersection(roles):
		return ""
	if "Legal Opinion Requester" in roles:
		return (
			"EXISTS (SELECT 1 FROM `tabLegal Opinion Request` req "
			"WHERE req.name = `tabLegal Opinion`.`opinion_request` "
			f"AND req.requested_by = {frappe.db.escape(user)})"
		)
	return "1=0"


def legal_opinion_has_permission(doc=None, ptype=None, user=None, **kwargs):
	if not doc:
		return True
	user = user or frappe.session.user
	if user == "Administrator" or PRIVILEGED.intersection(_roles(user)):
		return True
	roles = _roles(user)
	if {
		"Legal Department Manager",
		"Legal Opinion Officer",
		"Legal Officer",
		"Authorized Decision Maker",
	}.intersection(roles) or AUDIT_ROLES.intersection(roles):
		return True
	if "Legal Opinion Requester" in roles:
		requested_by = frappe.db.get_value(
			"Legal Opinion Request", doc.get("opinion_request"), "requested_by"
		)
		return requested_by == user and ptype in OWN_READ_TYPES
	return False


def _linked_grievance_condition(doctype):
	def query(user=None):
		condition = grievance_scope_sql(user, table="g")
		if condition is None:
			return ""
		table = f"`tab{doctype}`"
		return (
			f"({table}.`related_grievance` IS NULL "
			f"OR {table}.`related_grievance` = '' "
			"OR EXISTS (SELECT 1 FROM `tabEmployee Legal Grievance` g "
			f"WHERE g.name = {table}.`related_grievance` AND {condition}))"
		)

	return query


legal_correspondence_query = _linked_grievance_condition("Legal Correspondence")
legal_document_query = _linked_grievance_condition("Legal Document Register")
legal_expense_query = _linked_grievance_condition("Legal Expense")


def _linked_grievance_has_permission(doc=None, ptype=None, user=None, **kwargs):
	if not doc:
		return True
	grievance = doc.get("related_grievance")
	if not grievance:
		return True
	try:
		parent = frappe.get_doc("Employee Legal Grievance", grievance)
	except frappe.DoesNotExistError:
		return False
	return grievance_has_permission(parent, "read", user)


legal_correspondence_has_permission = _linked_grievance_has_permission
legal_document_has_permission = _linked_grievance_has_permission
legal_expense_has_permission = _linked_grievance_has_permission
