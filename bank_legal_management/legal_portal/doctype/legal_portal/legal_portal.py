import frappe
from frappe import _
from frappe.model.document import Document

DEFAULT_INTRO = _(
	"بوابة الدخول لإدارة الشؤون القانونية: تبدأ من هنا لتقديم شكوى، أو متابعة شكاوى "
	"موظف، أو الاطلاع على مستجدات القضايا والعقود والآراء."
)

DEFAULT_GUIDANCE = _(
	"لتقديم شكوى: افتح «شكوى موظف» ثم اختر جهة الاختصاص (إدارة الشؤون القانونية أو لجنة "
	"شكاوى الموظفين) قبل التقديم. تُحفظ كل الإجراءات في سجل إجراءات غير قابل للتعديل، "
	"ولا تُقبل التعديلات المباشرة بعد التقديم."
)


class LegalPortal(Document):
	def before_insert(self):
		self.set_default_content()

	def on_update(self):
		frappe.clear_cache(doctype=self.doctype)

	def validate(self):
		self.set_default_content()

	def set_default_content(self):
		if not self.intro:
			self.intro = DEFAULT_INTRO
		if not self.grievance_guidance:
			self.grievance_guidance = DEFAULT_GUIDANCE
