import frappe
from frappe import _
from frappe.model.document import Document


class LegalReminderLog(Document):
	def before_insert(self):
		if not self.alert_key:
			self.alert_key = f"{self.alert_type}:{self.reference_doctype}:{self.reference_name}:{frappe.utils.now()}"

	def validate(self):
		if self.is_new() and self.status not in ("Queued", "Sent", "Skipped"):
			self.status = "Queued"
