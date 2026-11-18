import frappe
from frappe.utils import add_days, today

from bank_legal_management.tests.helpers import (
	COMMITTEE_PATH,
	LEGAL_PATH,
	LegalTestBase,
)


class TestLegalPermissions(LegalTestBase):
	def setUp(self):
		super().setUp()
		self.create_user("employee", ["Employee Grievance Submitter"])
		self.create_user("other_employee", ["Employee Grievance Submitter"])
		self.create_user("legal_officer", ["Legal Grievance Officer"])
		self.create_user("legal_staff", ["Legal Officer"])
		self.create_user("legal_manager", ["Legal Grievance Manager"])
		self.create_user("committee_secretary", ["Employee Complaints Committee Secretary"])
		self.create_user("committee_chair", ["Employee Complaints Committee Chair"])
		self.create_user("committee_member", ["Employee Complaints Committee Member"])
		self.create_user("auditor", ["Legal Auditor"])
		self.create_user("admin", ["Legal System Administrator"])
		self.create_employee("employee", self.users["employee"])
		self.create_employee("other_employee", self.users["other_employee"])
		self.create_employee("legal_officer", self.users["legal_officer"])
		self.create_employee("chair", self.users["committee_chair"])
		self.create_employee("secretary", self.users["committee_secretary"])
		self.create_employee("member", self.users["committee_member"])

	# ------------------------------------------------------------------ scope
	def test_employee_sees_only_own_grievances(self):
		self.as_user("employee")
		own = self.create_grievance(submit=True)
		self.as_user("other_employee")
		other = self.create_grievance(submit=True)
		self.as_user("employee")
		names = [row.name for row in frappe.get_list("Employee Legal Grievance")]
		self.assertIn(own.name, names)
		self.assertNotIn(other.name, names)

	def test_legal_path_is_visible_to_legal_roles(self):
		self.as_user("employee")
		legal_case = self.create_grievance(jurisdiction=LEGAL_PATH, submit=True)
		self.as_user("other_employee")
		committee_case = self.create_grievance(jurisdiction=COMMITTEE_PATH, submit=True)
		self.as_user("legal_officer")
		names = [row.name for row in frappe.get_list("Employee Legal Grievance")]
		self.assertIn(legal_case.name, names)
		self.assertNotIn(committee_case.name, names)

	def test_committee_path_is_visible_to_committee_roles(self):
		self.as_user("employee")
		legal_case = self.create_grievance(jurisdiction=LEGAL_PATH, submit=True)
		self.as_user("other_employee")
		committee_case = self.create_grievance(jurisdiction=COMMITTEE_PATH, submit=True)
		self.as_user("committee_member")
		names = [row.name for row in frappe.get_list("Employee Legal Grievance")]
		self.assertIn(committee_case.name, names)
		self.assertNotIn(legal_case.name, names)

	def test_auditor_has_read_only_access(self):
		self.as_user("employee")
		grievance = self.create_grievance(submit=True)
		self.as_user("auditor")
		self.assertTrue(frappe.has_permission("Employee Legal Grievance", "read", grievance))
		self.assertFalse(frappe.has_permission("Employee Legal Grievance", "write", grievance))
		self.assertFalse(frappe.has_permission("Employee Legal Grievance", "submit", grievance))

	def test_legal_administrator_has_full_access(self):
		self.as_user("employee")
		grievance = self.create_grievance(submit=True)
		self.as_user("admin")
		for ptype in ("read", "write", "submit", "cancel", "delete"):
			self.assertTrue(
				frappe.has_permission("Employee Legal Grievance", ptype, grievance),
				msg=f"{ptype} should be allowed for the legal administrator",
			)

	def test_export_is_restricted_for_submitters(self):
		self.as_user("employee")
		grievance = self.create_grievance(submit=True)
		self.assertFalse(frappe.has_permission("Employee Legal Grievance", "export", grievance))
		self.as_user("legal_officer")
		self.assertTrue(frappe.has_permission("Employee Legal Grievance", "export", grievance))

	# -------------------------------------------------------------------- api
	def test_api_denies_timeline_for_unrelated_user(self):
		from bank_legal_management.api import get_grievance_timeline

		self.as_user("employee")
		grievance = self.create_grievance(submit=True)
		self.as_user("other_employee")
		self.assertRaises(frappe.PermissionError, get_grievance_timeline, grievance.name)

	def test_api_timeline_is_available_to_legal_roles(self):
		from bank_legal_management.api import get_grievance_timeline

		self.as_user("employee")
		grievance = self.create_grievance(submit=True)
		self.as_user("legal_officer")
		timeline = get_grievance_timeline(grievance.name)
		self.assertEqual(timeline["name"], grievance.name)
		self.assertEqual([row["action"] for row in timeline["actions"]], ["Submit"])

	def test_api_rejects_invalid_action(self):
		from bank_legal_management.api import apply_grievance_action

		self.as_user("employee")
		grievance = self.create_grievance(submit=True)
		self.as_user("legal_officer")
		self.assertRaises(
			frappe.ValidationError,
			apply_grievance_action,
			grievance.name,
			"Unknown Action",
		)

	def test_api_actions_require_submitted_grievance(self):
		from bank_legal_management.api import apply_grievance_action

		self.as_user("employee")
		grievance = self.create_grievance()
		self.as_user("legal_officer")
		self.assertRaises(
			frappe.PermissionError,
			apply_grievance_action,
			grievance.name,
			"Accept",
		)

	def test_api_issue_decision_requires_role(self):
		from bank_legal_management.api import issue_grievance_decision

		self.as_user("employee")
		grievance = self.create_grievance(submit=True)
		self.as_user("legal_officer")
		grievance.reload()
		grievance.apply_grievance_action("Accept")
		grievance.apply_grievance_action(
			"Prepare Legal Recommendation", recommendation="توصية"
		)
		grievance.apply_grievance_action("Refer for Decision")
		self.assertRaises(
			frappe.PermissionError,
			issue_grievance_decision,
			grievance.name,
			"قرار",
		)

	# ----------------------------------------------------------- attachments
	def test_attachments_of_legal_records_are_private(self):
		self.as_user("legal_staff")
		case = frappe.get_doc(
			{
				"doctype": "Legal Case",
				"case_title": "Attachment test",
				"case_type": "Civil",
				"registration_date": today(),
			}
		).insert()
		file = self.attach_file("Legal Case", case.name, "evidence.txt", is_private=0)
		self.assertEqual(file.is_private, 1)

	def test_attachments_cannot_be_moved_between_records(self):
		self.as_user("legal_staff")
		case = frappe.get_doc(
			{
				"doctype": "Legal Case",
				"case_title": "Attachment move test",
				"case_type": "Civil",
				"registration_date": today(),
			}
		).insert()
		other = frappe.get_doc(
			{
				"doctype": "Legal Case",
				"case_title": "Second case",
				"case_type": "Civil",
				"registration_date": today(),
			}
		).insert()
		file = self.attach_file("Legal Case", case.name, "evidence2.txt", is_private=0)
		file.attached_to_name = other.name
		self.assertRaises(frappe.PermissionError, file.save)

	# --------------------------------------------------------------- related
	def test_related_documents_follow_grievance_scope(self):
		self.as_user("employee")
		legal_case = self.create_grievance(jurisdiction=LEGAL_PATH, submit=True)
		self.as_user("other_employee")
		committee_case = self.create_grievance(jurisdiction=COMMITTEE_PATH, submit=True)
		self.as_user("legal_officer")
		document = frappe.get_doc(
			{
				"doctype": "Legal Document Register",
				"document_title": "سجل مرتبط",
				"document_type": "Evidence",
				"related_grievance": legal_case.name,
			}
		).insert()
		self.assertTrue(
			frappe.has_permission("Legal Document Register", "read", document)
		)
		hidden = frappe.get_doc(
			{
				"doctype": "Legal Document Register",
				"document_title": "سجل آخر",
				"document_type": "Evidence",
				"related_grievance": committee_case.name,
			}
		).insert(ignore_permissions=True)
		self.assertFalse(
			frappe.has_permission("Legal Document Register", "read", hidden)
		)

	def test_action_log_follows_parent_grievance_scope(self):
		self.as_user("employee")
		grievance = self.create_grievance(submit=True)
		log = frappe.get_all(
			"Grievance Action Log", filters={"grievance": grievance.name}, pluck="name"
		)[0]
		self.as_user("other_employee")
		self.assertFalse(
			frappe.has_permission(
				"Grievance Action Log", "read", frappe.get_doc("Grievance Action Log", log)
			)
		)
		self.as_user("legal_officer")
		self.assertTrue(
			frappe.has_permission(
				"Grievance Action Log", "read", frappe.get_doc("Grievance Action Log", log)
			)
		)
