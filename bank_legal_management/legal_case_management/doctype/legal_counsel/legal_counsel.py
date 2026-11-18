import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate


class LegalCounsel(Document):
	def validate(self):
		if not self.counsel_name:
			frappe.throw(_("اسم المستشار أو المحامي مطلوب."))
		if self.counsel_type == "Internal" and not self.employee:
			frappe.throw(_("يجب تحديد الموظف للمستشار الداخلي."))
		if self.counsel_type == "External" and not (self.law_firm or self.supplier):
			frappe.throw(_("يجب تحديد مكتب المحاماة أو المورد للمستشار الخارجي."))
		if self.engagement_start and self.engagement_end:
			if getdate(self.engagement_start) > getdate(self.engagement_end):
				frappe.throw(_("تاريخ بداية التكليف يجب أن يسبق تاريخ النهاية."))
