import frappe
from frappe import _
from frappe.utils import getdate, now_datetime, today


LEGAL_ROLES = (
	"Legal System Administrator",
	"Legal Department Manager",
	"Legal Case Manager",
	"Legal Officer",
	"Legal Contract Officer",
	"Legal Opinion Officer",
	"Legal Document Officer",
	"Legal Expense Officer",
	"Legal Auditor",
	"Legal Grievance Officer",
	"Legal Grievance Manager",
	"Employee Grievance Submitter",
	"Employee Complaints Committee Chair",
	"Employee Complaints Committee Member",
	"Employee Complaints Committee Secretary",
	"Authorized Decision Maker",
	"Legal Opinion Requester",
)

GRIEVANCE_PATH_LEGAL = "Legal Department"
GRIEVANCE_PATH_COMMITTEE = "Employee Complaints Committee"
GRIEVANCE_PATHS = (GRIEVANCE_PATH_LEGAL, GRIEVANCE_PATH_COMMITTEE)


def is_system_admin(user=None):
	user = user or frappe.session.user
	return user == "Administrator" or "Legal System Administrator" in frappe.get_roles(user)


def has_any_role(roles, user=None):
	roles = set(roles or ())
	if not roles:
		return False
	user = user or frappe.session.user
	if user == "Administrator":
		return True
	return bool(roles.intersection(frappe.get_roles(user)))


def require_roles(roles):
	if not has_any_role(roles):
		frappe.throw(
			_("ليست لديك الصلاحية لتنفيذ هذا الإجراء."),
			frappe.PermissionError,
			title=_("صلاحية مرفوضة"),
		)


def get_employee_for_user(user=None):
	user = user or frappe.session.user
	employees = frappe.get_all(
		"Employee",
		filters={"user_id": user, "status": "Active"},
		pluck="name",
		limit=3,
	)
	if len(employees) > 1:
		frappe.throw(
			_("حساب المستخدم مرتبط بأكثر من سجل موظف. يجب تصحيح الربط قبل المتابعة."),
			title=_("ربط الموظف غير صالح"),
		)
	return employees[0] if employees else None


def get_user_for_employee(employee):
	if not employee:
		return None
	return frappe.db.get_value("Employee", employee, "user_id")


def get_employee_snapshot(employee):
	if not employee:
		return {}
	fields = ["employee_name", "department", "designation", "company"]
	if frappe.get_meta("Employee").has_field("employee_number"):
		fields.append("employee_number")
	values = frappe.db.get_value("Employee", employee, fields, as_dict=True) or frappe._dict()
	return {
		"employee_name": values.get("employee_name"),
		"department": values.get("department"),
		"designation": values.get("designation"),
		"company": values.get("company"),
		"employee_number": values.get("employee_number"),
	}


def get_settings():
	try:
		return frappe.get_cached_doc("Legal Settings")
	except Exception:
		return frappe._dict()


def get_default_currency(company=None):
	company = company or frappe.defaults.get_global_default("company")
	if company:
		currency = frappe.db.get_value("Company", company, "default_currency")
		if currency:
			return currency
	settings = get_settings()
	if settings.get("default_currency"):
		return settings.get("default_currency")
	return frappe.defaults.get_defaults().get("currency")


def get_company():
	return frappe.defaults.get_global_default("company") or (get_settings().get("default_company"))


def get_users_with_roles(roles):
	roles = set(roles or ())
	if not roles:
		return []
	rows = frappe.get_all(
		"Has Role",
		filters={"parenttype": "User", "role": ("in", list(roles))},
		fields=["parent"],
		distinct=True,
	)
	users = []
	for row in rows:
		if row.parent and row.parent not in users and is_user_enabled(row.parent):
			users.append(row.parent)
	return users


def is_user_enabled(user):
	return bool(frappe.db.get_value("User", user, "enabled")) and user not in (
		"Guest",
		"Administrator",
	)


def get_committee_queue_users(grievance=None):
	users = set()
	committee = grievance.get("committee") if grievance else None
	if committee:
		committee_doc = frappe.get_doc("Employee Complaints Committee", committee)
		for employee in (committee_doc.get("chair"), committee_doc.get("secretary")):
			user = get_user_for_employee(employee)
			if user and is_user_enabled(user):
				users.add(user)
	if not users:
		users.update(
			get_users_with_roles(
				{"Employee Complaints Committee Chair", "Employee Complaints Committee Secretary"}
			)
		)
	return users


def get_grievance_queue_users(grievance):
	if grievance.get("jurisdiction_type") == GRIEVANCE_PATH_LEGAL:
		return set(
			get_users_with_roles(
				{"Legal Grievance Officer", "Legal Grievance Manager", "Legal Department Manager"}
			)
		)
	if grievance.get("jurisdiction_type") == GRIEVANCE_PATH_COMMITTEE:
		return get_committee_queue_users(grievance)
	return set()


def get_grievance_employee_user(grievance):
	if grievance.get("raised_by_user") and is_user_enabled(grievance.raised_by_user):
		return grievance.raised_by_user
	return get_user_for_employee(grievance.get("employee"))


def create_generic_notification(user, document_type=None, document_name=None, subject=None):
	"""Create a deliberately generic notification without sensitive case details."""
	if not user or not is_user_enabled(user):
		return
	subject = subject or _("لديك تحديث في نظام الشؤون القانونية")
	content = _(
		"لديك تحديث يحتاج إلى اطلاع. يرجى تسجيل الدخول إلى نظام الشؤون القانونية لعرض السجل."
	)
	link = None
	if document_type and document_name:
		link = frappe.utils.get_url_to_form(document_type, document_name)
	try:
		notification = frappe.get_doc(
			{
				"doctype": "Notification Log",
				"subject": subject,
				"email_content": content,
				"for_user": user,
				"document_type": document_type,
				"document_name": document_name,
				"link": link,
			}
		)
		notification.insert(ignore_permissions=True)
	except Exception:
		frappe.log_error(
			title="Legal notification log failed",
			message=frappe.get_traceback(),
		)
		return

	settings = get_settings()
	if settings.get("enable_email_notifications"):
		try:
			frappe.sendmail(
				recipients=[user],
				subject=subject,
				message=f"<p>{content}</p>",
				now=False,
			)
		except Exception:
			frappe.log_error(
				title="Legal notification email failed",
				message=frappe.get_traceback(),
			)


def notify_users(users, document_type=None, document_name=None, subject=None):
	recipients = {user for user in (users or []) if is_user_enabled(user)}
	for user in recipients:
		create_generic_notification(user, document_type, document_name, subject)
	return recipients


def notify_grievance_transition(grievance, include_employee=True, extra_users=None):
	users = set(get_grievance_queue_users(grievance))
	if grievance.get("current_responsible"):
		users.add(grievance.current_responsible)
	if include_employee:
		employee_user = get_grievance_employee_user(grievance)
		if employee_user:
			users.add(employee_user)
	if extra_users:
		users.update(extra_users)
	users.discard(frappe.session.user)
	notify_users(
		users,
		grievance.doctype,
		grievance.name,
		_("تحديث على شكوى"),
	)


def notify_status_change(doc, users=None, subject=None):
	users = set(users or [])
	if doc.get("owner"):
		users.add(doc.owner)
	if doc.get("assigned_officer"):
		user = get_user_for_employee(doc.assigned_officer)
		if user:
			users.add(user)
	if doc.get("contract_owner"):
		user = get_user_for_employee(doc.contract_owner)
		if user:
			users.add(user)
	if doc.get("follow_up_owner"):
		user = get_user_for_employee(doc.follow_up_owner)
		if user:
			users.add(user)
	users.discard(frappe.session.user)
	notify_users(
		users,
		doc.doctype,
		doc.name,
		subject or _("تحديث حالة سجل قانوني"),
	)


def get_next_date(date_value, days):
	from frappe.utils import add_days

	return add_days(getdate(date_value), int(days or 0))


def format_status_date(value):
	return str(getdate(value)) if value else ""


def now():
	return now_datetime()


def current_today():
	return today()
