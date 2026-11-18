import os

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, today

LEGAL_PATH = "Legal Department"
COMMITTEE_PATH = "Employee Complaints Committee"


def unique_email(prefix):
	return f"{prefix}.{frappe.generate_hash(length=8).lower()}@example.com"


def unique_digits(length=8):
	raw = frappe.generate_hash(length=length)
	return "".join(str(ord(char) % 10) for char in raw)


class LegalTestBase(IntegrationTestCase):
	"""Base class that provisions legal users/employees inside the test transaction."""

	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		# tests provision several users per case, disable the site wide throttle
		frappe.local.conf.throttle_user_limit = 10000
		self.company = frappe.defaults.get_global_default("company")
		self.users = {}
		self.employees = {}
		self.digits = unique_digits()
		self.temp_files = []

	def tearDown(self):
		for path in self.temp_files:
			if os.path.exists(path):
				os.remove(path)
		self.temp_files = []
		frappe.db.rollback()
		frappe.set_user("Administrator")
		super().tearDown()

	# ------------------------------------------------------------------ helpers
	def create_user(self, key, roles, first_name="Legal Test"):
		email = unique_email(key)
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": first_name,
				"send_welcome_email": 0,
				"enabled": 1,
			}
		).insert(ignore_permissions=True)
		user.add_roles(*roles)
		frappe.cache.hdel("roles", email)
		self.users[key] = email
		return email

	def create_employee(self, key, user=None):
		digits = unique_digits()
		employee = frappe.get_doc(
			{
				"doctype": "Employee",
				"first_name": f"Legal{key}",
				"gender": "Male",
				"date_of_birth": "1990-01-01",
				"date_of_joining": "2020-01-01",
				"status": "Active",
				"company": self.company,
				"employee_number": f"LEGALT-{key}-{digits}",
				"libyan_national_id": f"1199{digits}"[:12],
			}
		).insert(ignore_permissions=True)
		if user:
			employee.user_id = user
			employee.save(ignore_permissions=True)
		self.employees[key] = employee.name
		return employee.name

	def as_user(self, key_or_email):
		email = self.users.get(key_or_email, key_or_email)
		frappe.set_user(email)
		return email

	def create_committee(self, status="Active"):
		chair = self.employees.get("chair")
		secretary = self.employees.get("secretary")
		member = self.employees.get("member")
		committee = frappe.get_doc(
			{
				"doctype": "Employee Complaints Committee",
				"committee_name": f"Test Committee {self.digits}",
				"start_date": today(),
				"end_date": add_days(today(), 365),
				"chair": chair,
				"secretary": secretary,
				"quorum_percent": 50,
				"members": [
					{"employee": chair, "active": 1, "membership_start": today()},
					{"employee": secretary, "active": 1, "membership_start": today()},
					{"employee": member, "active": 1, "membership_start": today()},
				],
			}
		).insert(ignore_permissions=True)
		if status == "Active":
			committee.status = "Active"
			committee.save(ignore_permissions=True)
		self.committee = committee.name
		return committee.name

	def create_grievance(
		self,
		employee=None,
		jurisdiction=LEGAL_PATH,
		title="Test grievance",
		submit=False,
		user=None,
	):
		if not employee:
			employee = self.employee_for_user(frappe.session.user) or self.employees.get(
				"employee"
			)
		doc = frappe.get_doc(
			{
				"doctype": "Employee Legal Grievance",
				"employee": employee,
				"grievance_title": title,
				"grievance_type": "Workplace",
				"grievance_details": "تفاصيل الشكوى في الاختبار",
				"jurisdiction_type": jurisdiction,
			}
		)
		if user:
			frappe.set_user(user)
		doc.insert()
		if submit:
			doc.submit()
		return doc

	def attach_file(self, doctype, name, filename="evidence.txt", is_private=0):
		folder = frappe.get_site_path("private", "files")
		os.makedirs(folder, exist_ok=True)
		path = os.path.join(folder, filename)
		with open(path, "w", encoding="utf-8") as handle:
			handle.write("test evidence")
		self.temp_files.append(path)
		return frappe.get_doc(
			{
				"doctype": "File",
				"file_name": filename,
				"file_url": f"/private/files/{filename}",
				"attached_to_doctype": doctype,
				"attached_to_name": name,
				"is_private": is_private,
			}
		).insert(ignore_permissions=True)

	def employee_for_user(self, user):
		for key, employee in self.employees.items():
			if frappe.db.get_value("Employee", employee, "user_id") == user:
				return employee
		return None

	def action_logs(self, grievance):
		return frappe.get_all(
			"Grievance Action Log",
			filters={"grievance": grievance.name},
			fields=["action", "previous_status", "new_status", "performed_by"],
			order_by="creation asc",
		)
