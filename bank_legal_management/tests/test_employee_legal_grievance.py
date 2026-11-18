import frappe
from frappe.utils import today

from bank_legal_management.tests.helpers import (
	COMMITTEE_PATH,
	LEGAL_PATH,
	LegalTestBase,
)


class TestEmployeeLegalGrievance(LegalTestBase):
	def setUp(self):
		super().setUp()
		self.create_user("employee", ["Employee Grievance Submitter"])
		self.create_user("other_employee", ["Employee Grievance Submitter"])
		self.create_user("legal_officer", ["Legal Grievance Officer"])
		self.create_user("legal_manager", ["Legal Grievance Manager", "Legal Department Manager"])
		self.create_user("committee_secretary", ["Employee Complaints Committee Secretary"])
		self.create_user("committee_chair", ["Employee Complaints Committee Chair"])
		self.create_user("committee_member", ["Employee Complaints Committee Member"])
		self.create_user("decision_maker", ["Authorized Decision Maker"])
		self.create_employee("employee", self.users["employee"])
		self.create_employee("other_employee", self.users["other_employee"])
		self.create_employee("legal_officer", self.users["legal_officer"])
		self.create_employee("chair", self.users["committee_chair"])
		self.create_employee("secretary", self.users["committee_secretary"])
		self.create_employee("member", self.users["committee_member"])

	# --------------------------------------------------------------- creation
	def test_employee_creates_draft_grievance(self):
		self.as_user("employee")
		grievance = self.create_grievance()
		self.assertEqual(grievance.status, "Draft")
		self.assertEqual(grievance.docstatus, 0)
		self.assertEqual(grievance.raised_by_user, self.users["employee"])
		self.assertEqual(grievance.employee, self.employees["employee"])

	def test_submission_requires_jurisdiction(self):
		self.as_user("employee")
		grievance = frappe.get_doc(
			{
				"doctype": "Employee Legal Grievance",
				"employee": self.employees["employee"],
				"grievance_title": "بدون جهة اختصاص",
				"grievance_type": "Workplace",
				"grievance_details": "تفاصيل",
			}
		)
		grievance.insert()
		self.assertRaises(frappe.ValidationError, grievance.submit)

	def test_employee_cannot_create_for_another_employee(self):
		self.as_user("employee")
		self.assertRaises(
			frappe.PermissionError,
			self.create_grievance,
			employee=self.employees["other_employee"],
		)

	def test_invalid_jurisdiction_is_rejected(self):
		self.as_user("employee")
		self.assertRaises(
			frappe.ValidationError,
			self.create_grievance,
			jurisdiction="HR Department",
		)

	def test_submission_creates_action_log(self):
		self.as_user("employee")
		grievance = self.create_grievance(submit=True)
		self.assertEqual(grievance.status, "Submitted")
		self.assertEqual(grievance.docstatus, 1)
		logs = self.action_logs(grievance)
		self.assertEqual(len(logs), 1)
		self.assertEqual(logs[0].action, "Submit")
		self.assertEqual(logs[0].performed_by, self.users["employee"])

	# -------------------------------------------------------------- protection
	def test_controlled_fields_cannot_be_edited_after_submit(self):
		self.as_user("employee")
		grievance = self.create_grievance(submit=True)
		self.as_user("legal_officer")
		grievance.reload()
		grievance.status = "Closed"
		self.assertRaises(frappe.PermissionError, grievance.save)

	def test_action_log_is_immutable(self):
		self.as_user("employee")
		grievance = self.create_grievance(submit=True)
		log = frappe.get_all(
			"Grievance Action Log", filters={"grievance": grievance.name}, pluck="name"
		)[0]
		doc = frappe.get_doc("Grievance Action Log", log)
		doc.notes = "تعديل يدوي"
		self.assertRaises(frappe.PermissionError, doc.save)

	def test_action_log_cannot_be_deleted(self):
		self.as_user("employee")
		grievance = self.create_grievance(submit=True)
		log = frappe.get_all(
			"Grievance Action Log", filters={"grievance": grievance.name}, pluck="name"
		)[0]
		self.assertRaises(frappe.PermissionError, frappe.delete_doc, "Grievance Action Log", log)

	# ------------------------------------------------------------ legal path
	def test_legal_officer_accepts_grievance(self):
		self.as_user("employee")
		grievance = self.create_grievance(submit=True)
		self.as_user("legal_officer")
		grievance.reload()
		grievance.apply_grievance_action("Accept")
		self.assertEqual(grievance.status, "Legal Review")
		self.assertIn("Accept", [log.action for log in self.action_logs(grievance)])

	def test_committee_member_cannot_act_on_legal_path(self):
		self.as_user("employee")
		grievance = self.create_grievance(submit=True)
		self.as_user("committee_member")
		grievance.reload()
		self.assertRaises(
			frappe.PermissionError, grievance.apply_grievance_action, "Accept"
		)

	def test_request_information_and_response(self):
		self.as_user("employee")
		grievance = self.create_grievance(submit=True)
		self.as_user("legal_officer")
		grievance.reload()
		grievance.apply_grievance_action("Accept")
		grievance.apply_grievance_action("Request Information", notes="وضح تاريخ الطلب")
		self.assertEqual(grievance.status, "Awaiting Information")
		self.assertEqual(len(grievance.clarifications), 1)
		self.assertEqual(grievance.clarifications[0].status, "Requested")

		self.as_user("employee")
		grievance.reload()
		grievance.provide_information("الرد التفصيلي للموظف")
		self.assertEqual(grievance.status, "Legal Review")
		self.assertEqual(grievance.clarifications[0].status, "Responded")

	def test_request_information_requires_notes(self):
		self.as_user("employee")
		grievance = self.create_grievance(submit=True)
		self.as_user("legal_officer")
		grievance.reload()
		grievance.apply_grievance_action("Accept")
		self.assertRaises(
			frappe.ValidationError, grievance.apply_grievance_action, "Request Information"
		)

	def test_other_employee_cannot_provide_information(self):
		self.as_user("employee")
		grievance = self.create_grievance(submit=True)
		self.as_user("legal_officer")
		grievance.reload()
		grievance.apply_grievance_action("Accept")
		grievance.apply_grievance_action("Request Information", notes="مطلوب رد")
		self.as_user("other_employee")
		grievance.reload()
		self.assertRaises(
			frappe.PermissionError, grievance.provide_information, "رد غير مسموح"
		)

	def test_resume_review(self):
		self.as_user("employee")
		grievance = self.create_grievance(submit=True)
		self.as_user("legal_officer")
		grievance.reload()
		grievance.apply_grievance_action("Accept")
		grievance.apply_grievance_action("Request Information", notes="مطلوب رد")
		grievance.apply_grievance_action("Resume Review")
		self.assertEqual(grievance.status, "Legal Review")

	def test_legal_recommendation_requires_text(self):
		self.as_user("employee")
		grievance = self.create_grievance(submit=True)
		self.as_user("legal_officer")
		grievance.reload()
		grievance.apply_grievance_action("Accept")
		self.assertRaises(
			frappe.ValidationError,
			grievance.apply_grievance_action,
			"Prepare Legal Recommendation",
		)

	def test_refer_for_decision_requires_recommendation(self):
		self.as_user("employee")
		grievance = self.create_grievance(submit=True)
		self.as_user("legal_officer")
		grievance.reload()
		grievance.apply_grievance_action("Accept")
		self.assertRaises(
			frappe.ValidationError, grievance.apply_grievance_action, "Refer for Decision"
		)

	def test_decision_requires_authorized_role(self):
		self.as_user("employee")
		grievance = self.create_grievance(submit=True)
		self.as_user("legal_officer")
		grievance.reload()
		grievance.apply_grievance_action("Accept")
		grievance.apply_grievance_action(
			"Prepare Legal Recommendation", recommendation="توصية قانونية"
		)
		grievance.apply_grievance_action("Refer for Decision")
		self.assertEqual(grievance.status, "Pending Decision")
		self.as_user("legal_officer")
		grievance.reload()
		self.assertRaises(frappe.PermissionError, grievance.issue_decision, "قرار")

	def test_decision_separation_blocks_self_approval(self):
		hybrid = self.create_user("hybrid", ["Legal Grievance Officer", "Authorized Decision Maker"])
		self.as_user("employee")
		grievance = self.create_grievance(submit=True)
		self.as_user(hybrid)
		grievance.reload()
		grievance.apply_grievance_action("Accept")
		grievance.apply_grievance_action(
			"Prepare Legal Recommendation", recommendation="توصية قانونية"
		)
		grievance.apply_grievance_action("Refer for Decision")
		self.assertEqual(grievance.status, "Pending Decision")
		grievance.reload()
		self.assertRaises(frappe.PermissionError, grievance.issue_decision, "قرار")

	def test_issue_decision_creates_legal_decision(self):
		self.as_user("employee")
		grievance = self.create_grievance(submit=True)
		self.as_user("legal_officer")
		grievance.reload()
		grievance.apply_grievance_action("Accept")
		grievance.apply_grievance_action(
			"Prepare Legal Recommendation", recommendation="توصية قانونية"
		)
		grievance.apply_grievance_action("Refer for Decision")
		self.as_user("decision_maker")
		grievance.reload()
		result = grievance.issue_decision("نص القرار النهائي")
		self.assertEqual(result["status"], "Decision Issued")
		decision = frappe.get_doc("Legal Decision", result["decision"])
		self.assertEqual(decision.decision_type, "Employee Legal Grievance")
		self.assertEqual(decision.reference_name, grievance.name)
		self.assertEqual(decision.status, "Approved")
		self.assertIn("Issue Decision", [log.action for log in self.action_logs(grievance)])

	def test_close_requires_decision_and_reason(self):
		self.as_user("employee")
		grievance = self.create_grievance(submit=True)
		self.as_user("legal_officer")
		grievance.reload()
		grievance.apply_grievance_action("Accept")
		grievance.apply_grievance_action(
			"Prepare Legal Recommendation", recommendation="توصية قانونية"
		)
		grievance.apply_grievance_action("Refer for Decision")
		self.as_user("decision_maker")
		grievance.reload()
		grievance.issue_decision("نص القرار")
		self.as_user("legal_manager")
		grievance.reload()
		self.assertRaises(
			frappe.ValidationError, grievance.apply_grievance_action, "Close", notes=""
		)
		grievance.apply_grievance_action("Close", notes="تم التنفيذ")
		self.assertEqual(grievance.status, "Closed")
		self.assertEqual(grievance.closure_reason, "تم التنفيذ")

	# --------------------------------------------------------- jurisdiction
	def test_transfer_jurisdiction_requires_reason(self):
		self.as_user("employee")
		grievance = self.create_grievance(submit=True)
		self.as_user("legal_manager")
		grievance.reload()
		self.assertRaises(
			frappe.ValidationError,
			grievance.transfer_jurisdiction,
			COMMITTEE_PATH,
			"",
		)

	def test_transfer_jurisdiction_moves_to_committee_path(self):
		self.create_committee()
		self.as_user("employee")
		grievance = self.create_grievance(submit=True)
		self.as_user("legal_manager")
		grievance.reload()
		grievance.transfer_jurisdiction(COMMITTEE_PATH, "التصعيد إلى اللجنة")
		self.assertEqual(grievance.jurisdiction_type, COMMITTEE_PATH)
		self.assertEqual(grievance.status, "Submitted")
		self.assertEqual(grievance.original_jurisdiction, LEGAL_PATH)
		self.assertIn(
			"Transfer Jurisdiction", [log.action for log in self.action_logs(grievance)]
		)

	# -------------------------------------------------------- committee path
	def test_committee_path_full_flow(self):
		self.create_committee()
		self.as_user("employee")
		grievance = self.create_grievance(jurisdiction=COMMITTEE_PATH, submit=True)
		self.as_user("committee_secretary")
		grievance.reload()
		grievance.apply_grievance_action("Accept")
		self.assertEqual(grievance.status, "Committee Review")
		self.assertEqual(grievance.committee, self.committee)
		grievance.apply_grievance_action(
			"Prepare Committee Recommendation", recommendation="توصية اللجنة"
		)
		self.assertEqual(grievance.status, "Committee Recommendation")
		grievance.apply_grievance_action("Refer for Decision")
		self.assertEqual(grievance.status, "Pending Decision")
		self.as_user("decision_maker")
		grievance.reload()
		result = grievance.issue_decision("قرار اللجنة")
		self.assertEqual(result["status"], "Decision Issued")
		self.as_user("committee_secretary")
		grievance.reload()
		grievance.apply_grievance_action("Close", notes="تم الإغلاق")
		self.assertEqual(grievance.status, "Closed")

	def test_committee_path_rejects_legal_only_actions(self):
		self.create_committee()
		self.as_user("employee")
		grievance = self.create_grievance(jurisdiction=COMMITTEE_PATH, submit=True)
		self.as_user("committee_secretary")
		grievance.reload()
		grievance.apply_grievance_action("Accept")
		self.assertRaises(
			frappe.ValidationError,
			grievance.apply_grievance_action,
			"Prepare Legal Recommendation",
			recommendation="توصية",
		)

	# ------------------------------------------------------------- settings
	def test_on_behalf_requires_enabled_setting(self):
		self.as_user("legal_officer")
		self.assertRaises(
			frappe.PermissionError,
			self.create_grievance,
			employee=self.employees["other_employee"],
		)

	def test_on_behalf_allowed_when_setting_enabled(self):
		settings = frappe.get_doc("Legal Settings")
		settings.allow_grievance_on_behalf = 1
		settings.save(ignore_permissions=True)
		self.as_user("legal_manager")
		grievance = self.create_grievance(
			employee=self.employees["other_employee"], user=self.users["legal_manager"]
		)
		self.assertEqual(grievance.submitted_on_behalf, 1)
		self.assertEqual(grievance.raised_by_user, self.users["legal_manager"])

	def test_available_actions_depend_on_role_and_state(self):
		self.as_user("employee")
		grievance = self.create_grievance(submit=True)
		self.as_user("legal_officer")
		grievance.reload()
		actions = [item["action"] for item in grievance.get_available_grievance_actions()]
		self.assertIn("Accept", actions)
		self.assertNotIn("Issue Decision", actions)
		self.as_user("decision_maker")
		grievance.reload()
		self.assertRaises(
			frappe.PermissionError, grievance.get_available_grievance_actions
		)
		self.as_user("legal_officer")
		grievance.reload()
		grievance.apply_grievance_action("Accept")
		grievance.apply_grievance_action(
			"Prepare Legal Recommendation", recommendation="توصية قانونية"
		)
		grievance.apply_grievance_action("Refer for Decision")
		self.as_user("decision_maker")
		grievance.reload()
		actions = [item["action"] for item in grievance.get_available_grievance_actions()]
		self.assertEqual(actions, ["Issue Decision"])

	def test_target_completion_and_dates_are_set_on_submit(self):
		self.as_user("employee")
		grievance = self.create_grievance(submit=True)
		self.assertTrue(grievance.referral_date)
		self.assertTrue(grievance.request_date)
		self.assertLessEqual(grievance.request_date, today())
