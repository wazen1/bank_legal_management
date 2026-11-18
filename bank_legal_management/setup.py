import frappe
from frappe import _

ROLES = [
	("Legal System Administrator", 1),
	("Legal Department Manager", 1),
	("Legal Officer", 1),
	("Legal Case Manager", 1),
	("Legal Contract Officer", 1),
	("Legal Opinion Officer", 1),
	("Legal Document Officer", 1),
	("Legal Expense Officer", 1),
	("Legal Auditor", 1),
	("Legal Opinion Requester", 1),
	("Employee Grievance Submitter", 1),
	("Legal Grievance Officer", 1),
	("Legal Grievance Manager", 1),
	("Employee Complaints Committee Chair", 1),
	("Employee Complaints Committee Member", 1),
	("Employee Complaints Committee Secretary", 1),
	("Authorized Decision Maker", 1),
]


CHART_DEFINITIONS = [
	{
		"chart_name": "القضايا حسب الحالة",
		"document_type": "Legal Case",
		"chart_type": "Group By",
		"group_by_type": "Count",
		"group_by_based_on": "status",
		"type": "Bar",
	},
	{
		"chart_name": "العقود حسب الحالة",
		"document_type": "Legal Contract",
		"chart_type": "Group By",
		"group_by_type": "Count",
		"group_by_based_on": "status",
		"type": "Bar",
	},
	{
		"chart_name": "الشكاوى حسب الحالة",
		"document_type": "Employee Legal Grievance",
		"chart_type": "Group By",
		"group_by_type": "Count",
		"group_by_based_on": "status",
		"type": "Donut",
	},
	{
		"chart_name": "الشكاوى حسب جهة الاختصاص",
		"document_type": "Employee Legal Grievance",
		"chart_type": "Group By",
		"group_by_type": "Count",
		"group_by_based_on": "jurisdiction_type",
		"type": "Pie",
	},
	{
		"chart_name": "المصروفات حسب النوع",
		"document_type": "Legal Expense",
		"chart_type": "Group By",
		"group_by_type": "Sum",
		"group_by_based_on": "expense_type",
		"aggregate_function_based_on": "amount",
		"type": "Bar",
	},
]


NUMBER_CARD_DEFINITIONS = [
	{
		"label": "القضايا المفتوحة",
		"document_type": "Legal Case",
		"function": "Count",
		"filters_json": '[["status", "not in", ["Closed", "Archived"]]]',
	},
	{
		"label": "العقود النشطة",
		"document_type": "Legal Contract",
		"function": "Count",
		"filters_json": '[["status", "in", ["Active", "Expiring"]]]',
	},
	{
		"label": "الشكاوى المفتوحة",
		"document_type": "Employee Legal Grievance",
		"function": "Count",
		"filters_json": '[["docstatus", "=", 1], ["status", "not in", ["Closed", "Rejected"]]]',
	},
	{
		"label": "قرارات قيد الانتظار",
		"document_type": "Employee Legal Grievance",
		"function": "Count",
		"filters_json": '[["docstatus", "=", 1], ["status", "=", "Pending Decision"]]',
	},
	{
		"label": "الجلسات القادمة",
		"document_type": "Legal Hearing",
		"function": "Count",
		"filters_json": '[["status", "=", "Scheduled"], ["hearing_date", ">=", "Today"]]',
	},
	{
		"label": "طلبات الرأي المفتوحة",
		"document_type": "Legal Opinion Request",
		"function": "Count",
		"filters_json": '[["status", "not in", ["Approved", "Rejected", "Closed", "Cancelled"]]]',
	},
	{
		"label": "اللجان النشطة",
		"document_type": "Employee Complaints Committee",
		"function": "Count",
		"filters_json": '[["status", "=", "Active"]]',
	},
]


WORKFLOW_STATE_STYLES = {
	"Draft": "Info",
	"Registered": "Info",
	"Under Review": "Warning",
	"Assigned": "Info",
	"In Progress": "Primary",
	"Hearing Scheduled": "Primary",
	"Awaiting Documents": "Warning",
	"Awaiting Judgment": "Warning",
	"Judgment Issued": "Success",
	"Under Appeal": "Warning",
	"Settled": "Success",
	"Closed": "Success",
	"Archived": "Info",
	"Under Legal Review": "Warning",
	"Returned for Amendment": "Danger",
	"Pending Approval": "Warning",
	"Pending Signature": "Warning",
	"Active": "Success",
	"Expiring": "Warning",
	"Renewed": "Success",
	"Terminated": "Danger",
	"Expired": "Danger",
	"Submitted": "Info",
	"Awaiting Clarification": "Warning",
	"Draft Opinion": "Info",
	"Legal Review": "Warning",
	"Approved": "Success",
	"Rejected": "Danger",
	"Cancelled": "Danger",
}


CASE_WORKFLOW_STATES = [
	("Draft", "Legal Case Manager"),
	("Registered", "Legal Case Manager"),
	("Under Review", "Legal Case Manager"),
	("Assigned", "Legal Case Manager"),
	("In Progress", "Legal Case Manager"),
	("Hearing Scheduled", "Legal Case Manager"),
	("Awaiting Documents", "Legal Case Manager"),
	("Awaiting Judgment", "Legal Department Manager"),
	("Judgment Issued", "Legal Department Manager"),
	("Under Appeal", "Legal Department Manager"),
	("Settled", "Legal Department Manager"),
	("Closed", "Legal Department Manager"),
	("Archived", "Legal System Administrator"),
]

CASE_TRANSITIONS = [
	("Draft", "Register Case", "Registered", ["Legal Case Manager", "Legal Department Manager", "Legal Officer"]),
	("Registered", "Start Legal Review", "Under Review", ["Legal Case Manager", "Legal Department Manager", "Legal Officer"]),
	("Under Review", "Assign Case", "Assigned", ["Legal Case Manager", "Legal Department Manager", "Legal Officer"]),
	("Assigned", "Start Progress", "In Progress", ["Legal Case Manager", "Legal Department Manager", "Legal Officer"]),
	("In Progress", "Mark Hearing Scheduled", "Hearing Scheduled", ["Legal Case Manager", "Legal Department Manager", "Legal Officer"]),
	("In Progress", "Request Documents", "Awaiting Documents", ["Legal Case Manager", "Legal Department Manager", "Legal Officer"]),
	("In Progress", "Await Judgment", "Awaiting Judgment", ["Legal Case Manager", "Legal Department Manager", "Legal Officer"]),
	("In Progress", "Mark Settled", "Settled", ["Legal Department Manager"]),
	("In Progress", "Close Case", "Closed", ["Legal Department Manager"]),
	("Hearing Scheduled", "Resume Case", "In Progress", ["Legal Case Manager", "Legal Department Manager", "Legal Officer"]),
	("Hearing Scheduled", "Await Judgment", "Awaiting Judgment", ["Legal Case Manager", "Legal Department Manager", "Legal Officer"]),
	("Awaiting Documents", "Resume Work", "In Progress", ["Legal Case Manager", "Legal Department Manager", "Legal Officer"]),
	("Awaiting Documents", "Mark Hearing Scheduled", "Hearing Scheduled", ["Legal Case Manager", "Legal Department Manager", "Legal Officer"]),
	("Awaiting Judgment", "Record Judgment", "Judgment Issued", ["Legal Case Manager", "Legal Department Manager", "Legal Officer"]),
	("Judgment Issued", "File Appeal", "Under Appeal", ["Legal Case Manager", "Legal Department Manager"]),
	("Judgment Issued", "Record Settlement", "Settled", ["Legal Department Manager"]),
	("Judgment Issued", "Close Case", "Closed", ["Legal Department Manager"]),
	("Under Appeal", "Record Appeal Judgment", "Judgment Issued", ["Legal Department Manager"]),
	("Under Appeal", "Record Settlement", "Settled", ["Legal Department Manager"]),
	("Under Appeal", "Close Case", "Closed", ["Legal Department Manager"]),
	("Settled", "Close Case", "Closed", ["Legal Department Manager"]),
	("Closed", "Archive Case", "Archived", ["Legal System Administrator"]),
]

CONTRACT_WORKFLOW_STATES = [
	("Draft", "Legal Contract Officer"),
	("Under Legal Review", "Legal Officer"),
	("Returned for Amendment", "Legal Contract Officer"),
	("Pending Approval", "Legal Department Manager"),
	("Pending Signature", "Legal Contract Officer"),
	("Active", "Legal Contract Officer"),
	("Expiring", "Legal Contract Officer"),
	("Renewed", "Legal Department Manager"),
	("Terminated", "Legal Department Manager"),
	("Expired", "Legal Department Manager"),
	("Archived", "Legal System Administrator"),
]

CONTRACT_TRANSITIONS = [
	("Draft", "Send for Legal Review", "Under Legal Review", ["Legal Contract Officer", "Legal Officer", "Legal Department Manager"]),
	("Under Legal Review", "Return for Amendment", "Returned for Amendment", ["Legal Officer", "Legal Department Manager"]),
	("Under Legal Review", "Send for Approval", "Pending Approval", ["Legal Officer", "Legal Department Manager"]),
	("Returned for Amendment", "Resubmit for Review", "Under Legal Review", ["Legal Contract Officer", "Legal Officer"]),
	("Pending Approval", "Approve Contract", "Pending Signature", ["Legal Department Manager"]),
	("Pending Approval", "Return for Amendment", "Returned for Amendment", ["Legal Department Manager"]),
	("Pending Signature", "Activate Contract", "Active", ["Legal Contract Officer", "Legal Department Manager"]),
	("Active", "Mark Expiring", "Expiring", ["Legal Contract Officer", "Legal Department Manager"]),
	("Active", "Terminate Contract", "Terminated", ["Legal Department Manager"]),
	("Active", "Mark Expired", "Expired", ["Legal Department Manager"]),
	("Expiring", "Terminate Contract", "Terminated", ["Legal Department Manager"]),
	("Expiring", "Mark Expired", "Expired", ["Legal Department Manager"]),
	("Expiring", "Mark Renewed", "Renewed", ["Legal Department Manager"]),
	("Renewed", "Archive Contract", "Archived", ["Legal System Administrator", "Legal Department Manager"]),
	("Terminated", "Archive Contract", "Archived", ["Legal System Administrator", "Legal Department Manager"]),
	("Expired", "Archive Contract", "Archived", ["Legal System Administrator", "Legal Department Manager"]),
]

OPINION_WORKFLOW_STATES = [
	("Draft", "Legal Opinion Requester"),
	("Submitted", "Legal Opinion Officer"),
	("Under Review", "Legal Opinion Officer"),
	("Awaiting Clarification", "Legal Opinion Requester"),
	("Draft Opinion", "Legal Opinion Officer"),
	("Legal Review", "Legal Department Manager"),
	("Pending Approval", "Authorized Decision Maker"),
	("Approved", "Legal Department Manager"),
	("Rejected", "Legal Department Manager"),
	("Closed", "Legal Department Manager"),
	("Cancelled", "Legal Opinion Requester"),
]

OPINION_TRANSITIONS = [
	("Draft", "Submit for Review", "Submitted", ["Legal Opinion Requester", "Legal Opinion Officer", "Legal Officer"]),
	("Submitted", "Start Review", "Under Review", ["Legal Opinion Officer", "Legal Officer"]),
	("Submitted", "Reject Request", "Rejected", ["Legal Department Manager"]),
	("Under Review", "Request Clarification", "Awaiting Clarification", ["Legal Opinion Officer", "Legal Officer"]),
	("Under Review", "Draft Opinion", "Draft Opinion", ["Legal Opinion Officer", "Legal Officer"]),
	("Under Review", "Send for Approval", "Pending Approval", ["Legal Opinion Officer", "Legal Department Manager"]),
	("Awaiting Clarification", "Submit Clarification", "Under Review", ["Legal Opinion Requester", "Legal Opinion Officer"]),
	("Draft Opinion", "Send for Legal Review", "Legal Review", ["Legal Opinion Officer", "Legal Officer"]),
	("Legal Review", "Return for Revision", "Draft Opinion", ["Legal Department Manager"]),
	("Legal Review", "Send for Approval", "Pending Approval", ["Legal Department Manager"]),
	("Pending Approval", "Approve Request", "Approved", ["Authorized Decision Maker"]),
	("Pending Approval", "Reject Request", "Rejected", ["Authorized Decision Maker"]),
	("Approved", "Close Request", "Closed", ["Legal Department Manager"]),
	("Rejected", "Close Request", "Closed", ["Legal Department Manager"]),
	("Draft", "Cancel Request", "Cancelled", ["Legal Opinion Requester"]),
]


def after_install():
	create_roles()
	create_workflow_masters()
	create_workflows()
	create_dashboard_data()
	configure_legal_settings()
	sync_workspace_cards()


def after_migrate():
	create_roles()
	create_workflow_masters()
	create_workflows()
	create_dashboard_data()
	configure_legal_settings()
	sync_workspace_cards()


def create_roles():
	for role, desk_access in ROLES:
		if not frappe.db.exists("Role", role):
			frappe.get_doc(
				{
					"doctype": "Role",
					"role_name": role,
					"desk_access": desk_access,
				}
			).insert(ignore_permissions=True)


def create_workflow_masters():
	states = set()
	actions = set()
	for rows in (CASE_WORKFLOW_STATES, CONTRACT_WORKFLOW_STATES, OPINION_WORKFLOW_STATES):
		for state, _edit in rows:
			states.add(state)
	for rows in (CASE_TRANSITIONS, CONTRACT_TRANSITIONS, OPINION_TRANSITIONS):
		for _state, action, _next_state, _roles in rows:
			actions.add(action)
	for state in states:
		if not frappe.db.exists("Workflow State", state):
			frappe.get_doc(
				{
					"doctype": "Workflow State",
					"workflow_state_name": state,
					"style": WORKFLOW_STATE_STYLES.get(state, "Info"),
				}
			).insert(ignore_permissions=True)
	for action in actions:
		if not frappe.db.exists("Workflow Action Master", action):
			frappe.get_doc(
				{
					"doctype": "Workflow Action Master",
					"workflow_action_name": action,
				}
			).insert(ignore_permissions=True)


def create_workflows():
	upsert_workflow(
		workflow_name="Legal Case Workflow",
		document_type="Legal Case",
		states=CASE_WORKFLOW_STATES,
		transitions=CASE_TRANSITIONS,
	)
	upsert_workflow(
		workflow_name="Legal Contract Workflow",
		document_type="Legal Contract",
		states=CONTRACT_WORKFLOW_STATES,
		transitions=CONTRACT_TRANSITIONS,
	)
	upsert_workflow(
		workflow_name="Legal Opinion Request Workflow",
		document_type="Legal Opinion Request",
		states=OPINION_WORKFLOW_STATES,
		transitions=OPINION_TRANSITIONS,
	)


def upsert_workflow(workflow_name, document_type, states, transitions):
	if not frappe.db.exists("DocType", document_type):
		return
	workflow = frappe.get_doc("Workflow", workflow_name) if frappe.db.exists("Workflow", workflow_name) else frappe.new_doc("Workflow")
	workflow.workflow_name = workflow_name
	workflow.document_type = document_type
	workflow.is_active = 1
	workflow.override_status = 0
	workflow.send_email_alert = 0
	workflow.workflow_state_field = "status"
	workflow.states = []
	for state, allow_edit in states:
		workflow.append(
			"states",
			{
				"state": state,
				"doc_status": "0",
				"allow_edit": allow_edit,
			},
		)
	workflow.transitions = []
	for state, action, next_state, roles in transitions:
		for role in list(roles) + ["Legal System Administrator"]:
			workflow.append(
				"transitions",
				{
					"state": state,
					"action": action,
					"next_state": next_state,
					"allowed": role,
					"allow_self_approval": 1,
				},
			)
	if workflow.is_new():
		workflow.insert(ignore_permissions=True)
	else:
		workflow.save(ignore_permissions=True)
	frappe.clear_cache(doctype=document_type)


def create_dashboard_data():
	for definition in CHART_DEFINITIONS:
		values = {
			"doctype": "Dashboard Chart",
			"chart_name": definition["chart_name"],
			"chart_type": definition["chart_type"],
			"document_type": definition["document_type"],
			"group_by_type": definition["group_by_type"],
			"group_by_based_on": definition["group_by_based_on"],
			"aggregate_function_based_on": definition.get("aggregate_function_based_on"),
			"type": definition["type"],
			"filters_json": "[]",
			"is_public": 1,
		}
		name = definition["chart_name"]
		if frappe.db.exists("Dashboard Chart", name):
			chart = frappe.get_doc("Dashboard Chart", name)
			if chart.get("document_type") != values["document_type"] or chart.get(
				"chart_type"
			) != values["chart_type"]:
				frappe.delete_doc("Dashboard Chart", name, force=1, ignore_doctypes=["Dashboard Chart"])
				frappe.get_doc(values).insert(ignore_permissions=True)
			else:
				chart.document_type = values["document_type"]
				chart.group_by_type = values["group_by_type"]
				chart.group_by_based_on = values["group_by_based_on"]
				chart.aggregate_function_based_on = values["aggregate_function_based_on"]
				chart.filters_json = values["filters_json"]
				chart.is_public = 1
				chart.save(ignore_permissions=True)
		else:
			frappe.get_doc(values).insert(ignore_permissions=True)
	for definition in NUMBER_CARD_DEFINITIONS:
		values = {
			"doctype": "Number Card",
			"label": definition["label"],
			"type": "Document Type",
			"document_type": definition["document_type"],
			"function": definition["function"],
			"filters_json": definition["filters_json"],
			"is_public": 1,
			"show_percentage_stats": 0,
		}
		name = definition["label"]
		if frappe.db.exists("Number Card", name):
			card = frappe.get_doc("Number Card", name)
			if card.get("document_type") != values["document_type"]:
				frappe.delete_doc("Number Card", name, force=1, ignore_doctypes=["Number Card"])
				frappe.get_doc(values).insert(ignore_permissions=True)
			else:
				card.function = values["function"]
				card.filters_json = values["filters_json"]
				card.is_public = 1
				card.show_percentage_stats = 0
				card.save(ignore_permissions=True)
		else:
			frappe.get_doc(values).insert(ignore_permissions=True)


def configure_legal_settings():
	if not frappe.db.exists("DocType", "Legal Settings"):
		return
	settings = frappe.get_doc("Legal Settings")
	changed = False
	if not settings.default_company:
		settings.default_company = frappe.defaults.get_global_default("company")
		changed = True
	if not settings.default_currency and settings.default_company:
		settings.default_currency = frappe.db.get_value(
			"Company", settings.default_company, "default_currency"
		)
		changed = True
	if changed:
		settings.flags.ignore_permissions = True
		settings.save(ignore_permissions=True)


def sync_workspace_cards():
	if not frappe.db.exists("DocType", "Workspace"):
		return
	if not frappe.db.exists("Workspace", "Legal Management"):
		return
	workspace = frappe.get_doc("Workspace", "Legal Management")
	if not workspace.title:
		workspace.title = "Legal Management"
	if not workspace.type:
		workspace.type = "Workspace"
	workspace.charts = []
	workspace.number_cards = []
	for definition in CHART_DEFINITIONS:
		if frappe.db.exists("Dashboard Chart", definition["chart_name"]):
			workspace.append(
				"charts",
				{
					"chart_name": definition["chart_name"],
					"label": definition["chart_name"],
				},
			)
	for definition in NUMBER_CARD_DEFINITIONS:
		if frappe.db.exists("Number Card", definition["label"]):
			workspace.append(
				"number_cards",
				{
					"number_card_name": definition["label"],
					"label": definition["label"],
				},
			)
	workspace.flags.ignore_permissions = True
	workspace.save(ignore_permissions=True)
