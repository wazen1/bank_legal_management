import frappe
from frappe.model.workflow import apply_workflow
from frappe.utils import add_days, today

from bank_legal_management.tests.helpers import COMMITTEE_PATH, LegalTestBase


class TestLegalRecords(LegalTestBase):
	def setUp(self):
		super().setUp()
		self.create_user("case_manager", ["Legal Case Manager"])
		self.create_user("legal_officer", ["Legal Officer"])
		self.create_user("contract_officer", ["Legal Contract Officer"])
		self.create_user("legal_manager", ["Legal Department Manager"])
		self.create_user("opinion_officer", ["Legal Opinion Officer"])
		self.create_user("requester", ["Legal Opinion Requester"])
		self.create_user("decision_maker", ["Authorized Decision Maker"])
		self.create_user("expense_officer", ["Legal Expense Officer"])
		self.create_user("committee_secretary", ["Employee Complaints Committee Secretary"])
		self.create_user("committee_member", ["Employee Complaints Committee Member"])
		self.create_user("committee_chair", ["Employee Complaints Committee Chair"])
		self.create_user("employee", ["Employee Grievance Submitter"])
		self.create_employee("employee", self.users["employee"])
		self.create_employee("officer", self.users["legal_officer"])
		self.create_employee("contract_owner", self.users["contract_officer"])
		self.create_employee("chair", self.users["committee_chair"])
		self.create_employee("secretary", self.users["committee_secretary"])
		self.create_employee("member", self.users["committee_member"])

	# ------------------------------------------------------------- legal case
	def create_case(self, user=None, title="قضية اختبار"):
		frappe.set_user(user or self.users["case_manager"])
		return frappe.get_doc(
			{
				"doctype": "Legal Case",
				"case_title": title,
				"case_type": "Civil",
				"registration_date": today(),
			}
		).insert()

	def test_case_starts_as_draft(self):
		case = self.create_case()
		self.assertEqual(case.status, "Draft")
		self.assertEqual(case.company, self.company)

	def test_case_workflow_transitions(self):
		case = self.create_case()
		apply_workflow(case, "Register Case")
		case.reload()
		self.assertEqual(case.status, "Registered")
		apply_workflow(case, "Start Legal Review")
		case.reload()
		self.assertEqual(case.status, "Under Review")

	def test_case_cannot_skip_states(self):
		case = self.create_case()
		self.assertRaises(
			frappe.ValidationError, apply_workflow, case, "Await Judgment"
		)

	def test_hearing_updates_case_dates(self):
		case = self.create_case()
		frappe.set_user(self.users["case_manager"])
		hearing = frappe.get_doc(
			{
				"doctype": "Legal Hearing",
				"legal_case": case.name,
				"hearing_date": add_days(today(), 10),
			}
		).insert()
		self.assertEqual(hearing.status, "Scheduled")
		case.reload()
		self.assertEqual(str(case.next_hearing_date), str(hearing.hearing_date))

	def test_hearing_cannot_be_created_for_missing_case(self):
		frappe.set_user(self.users["case_manager"])
		self.assertRaises(
			frappe.ValidationError,
			frappe.get_doc(
				{
					"doctype": "Legal Hearing",
					"legal_case": "LC-DOES-NOT-EXIST",
					"hearing_date": add_days(today(), 5),
				}
			).insert,
		)

	# ---------------------------------------------------------- legal contract
	def create_contract(self, user=None):
		frappe.set_user(user or self.users["contract_officer"])
		return frappe.get_doc(
			{
				"doctype": "Legal Contract",
				"contract_title": "عقد اختبار",
				"contract_type": "Service",
				"party_type": "Employee",
				"party": self.employees["contract_owner"],
				"party_name": "متعامل اختبار",
				"contract_owner": self.employees["contract_owner"],
				"start_date": today(),
				"end_date": add_days(today(), 365),
				"signed_contract": "/private/files/contract.pdf",
				"signature_date": today(),
			}
		).insert()

	def test_contract_starts_as_draft(self):
		contract = self.create_contract()
		self.assertEqual(contract.status, "Draft")
		self.assertEqual(contract.currency, frappe.db.get_value("Company", self.company, "default_currency"))

	def test_contract_requires_party_before_review(self):
		frappe.set_user(self.users["contract_officer"])
		contract = frappe.get_doc(
			{
				"doctype": "Legal Contract",
				"contract_title": "عقد بلا طرف",
				"contract_type": "Service",
				"contract_owner": self.employees["contract_owner"],
			}
		).insert()
		self.assertRaises(frappe.ValidationError, apply_workflow, contract, "Send for Legal Review")

	def test_contract_full_workflow(self):
		contract = self.create_contract()
		frappe.set_user(self.users["contract_officer"])
		apply_workflow(contract, "Send for Legal Review")
		contract.reload()
		frappe.set_user(self.users["legal_manager"])
		apply_workflow(contract, "Send for Approval")
		contract.reload()
		apply_workflow(contract, "Approve Contract")
		contract.reload()
		self.assertEqual(contract.status, "Pending Signature")
		frappe.set_user(self.users["contract_officer"])
		apply_workflow(contract, "Activate Contract")
		contract.reload()
		self.assertEqual(contract.status, "Active")
		self.assertTrue(contract.approved_by)
		self.assertTrue(contract.approval_history)

	def test_contract_activation_requires_dates(self):
		frappe.set_user(self.users["contract_officer"])
		contract = frappe.get_doc(
			{
				"doctype": "Legal Contract",
				"contract_title": "عقد بلا تواريخ",
				"contract_type": "Service",
				"party_type": "Employee",
				"party": self.employees["contract_owner"],
				"party_name": "متعامل اختبار",
				"contract_owner": self.employees["contract_owner"],
			}
		).insert()
		contract.status = "Active"
		self.assertRaises(frappe.ValidationError, contract.save)

	# ----------------------------------------------------- legal opinion request
	def test_opinion_request_requires_review_content(self):
		frappe.set_user(self.users["requester"])
		request = frappe.get_doc(
			{
				"doctype": "Legal Opinion Request",
				"request_title": "طلب رأي",
				"consultation_type": "Legal Opinion",
				"requested_by": self.users["requester"],
			}
		).insert()
		self.assertEqual(request.status, "Draft")
		self.assertRaises(frappe.ValidationError, apply_workflow, request, "Submit for Review")

	def test_opinion_request_flow(self):
		frappe.set_user(self.users["requester"])
		request = frappe.get_doc(
			{
				"doctype": "Legal Opinion Request",
				"request_title": "طلب رأي",
				"consultation_type": "Legal Opinion",
				"requested_by": self.users["requester"],
				"subject": "موضوع",
				"facts": "وقائع",
				"questions": "أسئلة",
			}
		).insert()
		apply_workflow(request, "Submit for Review")
		request.reload()
		self.assertEqual(request.status, "Submitted")
		frappe.set_user(self.users["opinion_officer"])
		apply_workflow(request, "Start Review")
		request.reload()
		request.final_opinion = "رأي قانوني"
		request.save()
		apply_workflow(request, "Draft Opinion")
		request.reload()
		self.assertEqual(request.status, "Draft Opinion")
		apply_workflow(request, "Send for Legal Review")
		request.reload()
		frappe.set_user(self.users["legal_manager"])
		apply_workflow(request, "Send for Approval")
		request.reload()
		self.assertEqual(request.status, "Pending Approval")
		frappe.set_user(self.users["decision_maker"])
		apply_workflow(request, "Approve Request")
		request.reload()
		self.assertEqual(request.status, "Approved")
		self.assertTrue(request.approved_by)

	def test_requester_cannot_edit_after_submission(self):
		frappe.set_user(self.users["requester"])
		request = frappe.get_doc(
			{
				"doctype": "Legal Opinion Request",
				"request_title": "طلب رأي",
				"consultation_type": "Legal Opinion",
				"requested_by": self.users["requester"],
				"subject": "موضوع",
				"facts": "وقائع",
				"questions": "أسئلة",
			}
		).insert()
		apply_workflow(request, "Submit for Review")
		request.reload()
		request.subject = "تعديل بعد التقديم"
		self.assertRaises(frappe.PermissionError, request.save)

	def test_clarification_flow(self):
		frappe.set_user(self.users["requester"])
		request = frappe.get_doc(
			{
				"doctype": "Legal Opinion Request",
				"request_title": "طلب رأي",
				"consultation_type": "Legal Opinion",
				"requested_by": self.users["requester"],
				"subject": "موضوع",
				"facts": "وقائع",
				"questions": "أسئلة",
			}
		).insert()
		apply_workflow(request, "Submit for Review")
		frappe.set_user(self.users["opinion_officer"])
		request.reload()
		apply_workflow(request, "Start Review")
		request.reload()
		request.request_clarification("نحتاج توضيحا")
		self.assertEqual(request.status, "Awaiting Clarification")
		frappe.set_user(self.users["requester"])
		request.reload()
		request.provide_clarification("التوضيح")
		self.assertEqual(request.status, "Under Review")

	# ------------------------------------------------------------- legal expense
	def test_expense_requires_approval_role(self):
		frappe.set_user(self.users["expense_officer"])
		expense = frappe.get_doc(
			{
				"doctype": "Legal Expense",
				"expense_date": today(),
				"expense_type": "Legal Fees",
				"amount": 500,
				"description": "أتعاب",
			}
		).insert()
		expense.submit_for_review()
		self.assertEqual(expense.status, "Pending Review")
		self.assertRaises(frappe.PermissionError, expense.approve_expense)

	def test_expense_full_flow(self):
		frappe.set_user(self.users["expense_officer"])
		expense = frappe.get_doc(
			{
				"doctype": "Legal Expense",
				"expense_date": today(),
				"expense_type": "Legal Fees",
				"amount": 750,
				"description": "أتعاب",
			}
		).insert()
		expense.submit_for_review()
		frappe.set_user(self.users["legal_manager"])
		expense.reload()
		expense.approve_expense()
		self.assertEqual(expense.status, "Approved")
		frappe.set_user(self.users["expense_officer"])
		expense.reload()
		expense.mark_paid()
		self.assertEqual(expense.status, "Paid")

	def test_expense_rejection_requires_reason(self):
		frappe.set_user(self.users["expense_officer"])
		expense = frappe.get_doc(
			{
				"doctype": "Legal Expense",
				"expense_date": today(),
				"expense_type": "Legal Fees",
				"amount": 100,
				"description": "أتعاب",
			}
		).insert()
		expense.submit_for_review()
		frappe.set_user(self.users["legal_manager"])
		expense.reload()
		self.assertRaises(frappe.ValidationError, expense.reject_expense, "")

	# ------------------------------------------------------- committee meeting
	def test_committee_meeting_quorum_and_minutes(self):
		committee = self.create_committee()
		frappe.set_user(self.users["committee_secretary"])
		meeting = frappe.get_doc(
			{
				"doctype": "Employee Complaints Committee Meeting",
				"committee": committee,
				"meeting_date": today(),
				"status": "Draft",
			}
		).insert()
		self.assertTrue(meeting.attendees)
		self.assertTrue(meeting.quorum_required)
		meeting.status = "Scheduled"
		meeting.save()
		meeting.reload()
		meeting.minutes = "محضر الاجتماع"
		meeting.status = "Completed"
		meeting.save()
		meeting.reload()
		self.assertEqual(meeting.status, "Completed")
		self.assertTrue(meeting.quorum_met)
		self.assertRaises(frappe.PermissionError, meeting.approve_minutes)
		frappe.set_user(self.users["committee_chair"])
		meeting.reload()
		meeting.approve_minutes()
		self.assertEqual(meeting.minutes_status, "Approved")

	def test_committee_meeting_rejects_duplicate_agenda(self):
		committee = self.create_committee()
		frappe.set_user(self.users["employee"])
		grievance = self.create_grievance(jurisdiction=COMMITTEE_PATH, submit=True)
		frappe.set_user(self.users["committee_secretary"])
		meeting = frappe.get_doc(
			{
				"doctype": "Employee Complaints Committee Meeting",
				"committee": committee,
				"meeting_date": today(),
				"grievances": [
					{"grievance": grievance.name},
					{"grievance": grievance.name},
				],
			}
		)
		self.assertRaises(frappe.ValidationError, meeting.insert)

	# --------------------------------------------------------------- decisions
	def test_approved_decision_cannot_be_modified(self):
		frappe.set_user(self.users["opinion_officer"])
		decision = frappe.get_doc(
			{
				"doctype": "Legal Decision",
				"decision_title": "قرار اختبار",
				"decision_type": "Policy",
				"status": "Draft Recommendation",
				"recommendation": "توصية",
			}
		).insert()
		frappe.set_user(self.users["decision_maker"])
		decision.reload()
		decision.status = "Pending Approval"
		decision.save()
		decision.reload()
		decision.status = "Approved"
		decision.final_decision = "نص القرار"
		decision.save()
		decision.reload()
		decision.final_decision = "تعديل"
		self.assertRaises(frappe.PermissionError, decision.save)

	# --------------------------------------------------------------- scheduler
	def test_deadline_task_creates_single_reminder(self):
		from bank_legal_management.tasks import process_legal_deadlines

		case = self.create_case()
		case.assigned_officer = self.employees["officer"]
		case.save()
		frappe.set_user(self.users["case_manager"])
		frappe.get_doc(
			{
				"doctype": "Legal Hearing",
				"legal_case": case.name,
				"hearing_date": add_days(today(), 2),
			}
		).insert()
		process_legal_deadlines()
		logs = frappe.get_all(
			"Legal Reminder Log", filters={"alert_type": "Hearing Reminder"}, pluck="name"
		)
		self.assertTrue(logs)
		process_legal_deadlines()
		logs_after = frappe.get_all(
			"Legal Reminder Log", filters={"alert_type": "Hearing Reminder"}, pluck="name"
		)
		self.assertEqual(len(logs), len(logs_after))
