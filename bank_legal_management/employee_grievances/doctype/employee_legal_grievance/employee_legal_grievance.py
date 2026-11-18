import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, now_datetime, today

from bank_legal_management.utils import (
	GRIEVANCE_PATH_COMMITTEE,
	GRIEVANCE_PATH_LEGAL,
	GRIEVANCE_PATHS,
	get_employee_for_user,
	get_employee_snapshot,
	get_grievance_employee_user,
	get_settings,
	get_user_for_employee,
	has_any_role,
	is_system_admin,
	notify_grievance_transition,
	notify_users,
	require_roles,
)

LEGAL_REVIEW_ROLES = {
	"Legal Grievance Officer",
	"Legal Grievance Manager",
	"Legal Department Manager",
}
COMMITTEE_WRITE_ROLES = {
	"Employee Complaints Committee Chair",
	"Employee Complaints Committee Secretary",
}
COMMITTEE_REVIEW_ROLES = {
	"Employee Complaints Committee Chair",
	"Employee Complaints Committee Secretary",
	"Employee Complaints Committee Member",
}
DECISION_ROLE = "Authorized Decision Maker"
ON_BEHALF_ROLES = {
	"Legal Grievance Officer",
	"Legal Grievance Manager",
	"Legal Department Manager",
	"Employee Complaints Committee Chair",
	"Employee Complaints Committee Secretary",
	"Legal System Administrator",
}
TERMINAL_STATUSES = {"Closed", "Rejected"}
ACTIVE_STATUSES = {
	"Submitted",
	"Legal Review",
	"Committee Review",
	"Awaiting Information",
	"Legal Recommendation",
	"Committee Recommendation",
	"Scheduled for Meeting",
	"Under Committee Deliberation",
	"Pending Decision",
	"Decision Issued",
}
PATH_STATUS = {
	GRIEVANCE_PATH_LEGAL: "Legal Review",
	GRIEVANCE_PATH_COMMITTEE: "Committee Review",
}


class EmployeeLegalGrievance(Document):
	def before_insert(self):
		self.status = "Draft"
		self.set_submitter()
		self.set_employee_snapshot()
		if not self.request_date:
			self.request_date = today()
		self.validate_jurisdiction_choice(optional=True)

	def validate(self):
		self.validate_employee()
		self.set_employee_snapshot()
		self.validate_jurisdiction_choice(optional=self.docstatus != 1)
		self.validate_controlled_changes()
		self.validate_terminal_state()

	def validate_employee(self):
		if not self.employee:
			frappe.throw(_("الموظف صاحب الشكوى مطلوب."))
		if not frappe.db.exists("Employee", self.employee):
			frappe.throw(_("سجل الموظف غير موجود."))
		if not self.grievance_title:
			frappe.throw(_("عنوان الشكوى مطلوب."))
		if not self.grievance_details:
			frappe.throw(_("تفاصيل الشكوى مطلوبة."))

	def set_submitter(self):
		if self.is_new() and self.raised_by_user and not is_system_admin():
			if self.raised_by_user != frappe.session.user:
				frappe.throw(
					_("لا يمكن إنشاء شكوى منسوبة إلى مستخدم آخر."),
					frappe.PermissionError,
				)
		own_employee = get_employee_for_user()
		settings = get_settings()
		authorized_on_behalf = has_any_role(ON_BEHALF_ROLES) and settings.get(
			"allow_grievance_on_behalf"
		)
		employee_user = get_user_for_employee(self.employee)

		if self.is_new():
			if not self.employee:
				if own_employee:
					self.employee = own_employee
				elif not (authorized_on_behalf or is_system_admin()):
					frappe.throw(_("لا يوجد سجل موظف مرتبط بحسابك. راجع إدارة الموارد البشرية."))
			if own_employee and self.employee == own_employee:
				self.raised_by_user = frappe.session.user
				self.submitted_on_behalf = 0
			elif is_system_admin():
				if not self.raised_by_user:
					self.raised_by_user = employee_user or frappe.session.user
				self.submitted_on_behalf = 1 if (employee_user and employee_user != frappe.session.user) else 0
			elif authorized_on_behalf:
				self.raised_by_user = frappe.session.user
				self.submitted_on_behalf = 1
			else:
				if self.employee != own_employee:
					frappe.throw(
						_("لا يمكنك تقديم شكوى نيابة عن موظف آخر."),
						frappe.PermissionError,
					)
				self.raised_by_user = frappe.session.user
				self.submitted_on_behalf = 0
		else:
			before = self.get_doc_before_save()
			if before and before.raised_by_user:
				self.raised_by_user = before.raised_by_user
			if before and before.submitted_on_behalf is not None:
				self.submitted_on_behalf = before.submitted_on_behalf

	def set_employee_snapshot(self):
		snapshot = get_employee_snapshot(self.employee)
		for fieldname, value in snapshot.items():
			if self.docstatus == 1 and self.get(fieldname):
				continue
			self.set(fieldname, value)

	def validate_jurisdiction_choice(self, optional=False):
		if not self.jurisdiction_type:
			if optional:
				return
			frappe.throw(
				_("يجب اختيار جهة الاختصاص قبل إرسال الشكوى: إدارة الشؤون القانونية أو لجنة شكاوى الموظفين."),
			)
		if self.jurisdiction_type not in GRIEVANCE_PATHS:
			frappe.throw(_("جهة الاختصاص المحددة غير صالحة."))

	def validate_controlled_changes(self):
		if self.is_new() or self.docstatus != 1:
			return
		before = self.get_doc_before_save()
		if not before or before.docstatus != 1:
			return
		if is_system_admin() or self.flags.grievance_controlled_update:
			return
		blocked = {
			"status",
			"jurisdiction_type",
			"committee",
			"current_responsible",
			"recommendation",
			"recommendation_prepared_by",
			"recommendation_date",
			"approved_decision",
			"decision_reference",
			"decision_by",
			"decision_date",
			"closure_date",
			"closure_reason",
			"last_committee_meeting",
		}
		for fieldname in blocked:
			if self.has_value_changed(fieldname):
				frappe.throw(
					_("لا يمكن تعديل الشكوى بعد تقديمها مباشرة. استخدم إجراءات الشكوى الموثقة."),
					frappe.PermissionError,
				)
		if before.status in TERMINAL_STATUSES:
			for df in self.meta.fields:
				if df.fieldtype in ("Section Break", "Column Break", "Tab Break"):
					continue
				if df.fieldname and self.has_value_changed(df.fieldname):
					frappe.throw(_("الشكوى المغلقة غير قابلة للتعديل."))

	def validate_terminal_state(self):
		if self.docstatus == 0 and self.status not in ("Draft",):
			frappe.throw(_("الشكوى غير المقدمة يجب أن تبقى مسودة."))
		if self.docstatus == 1 and self.status == "Draft" and self._action != "submit":
			frappe.throw(_("لا يمكن إبقاء شكوى مقدمة بحالة مسودة."))

	def before_submit(self):
		if self.status != "Draft":
			frappe.throw(_("لا يمكن إرسال الشكوى من حالتها الحالية."))
		self.validate_employee()
		self.validate_jurisdiction_choice(optional=False)
		if not frappe.db.get_value("Employee", self.employee, "status") == "Active":
			frappe.throw(_("لا يمكن تقديم شكوى لموظف غير نشط."))
		self.original_jurisdiction = self.jurisdiction_type
		self.referral_date = now_datetime()
		self.raised_by_user = self.raised_by_user or frappe.session.user
		self.status = "Submitted"
		if not self.target_completion_date:
			self.target_completion_date = None

	def on_submit(self):
		self._add_action_log(
			action="Submit",
			previous_status="Draft",
			new_status="Submitted",
			responsible_party=self._responsible_label(),
		)
		notify_grievance_transition(self)

	def before_cancel(self):
		if not is_system_admin():
			frappe.throw(
				_("إلغاء شكوى مقدمة يتطلب مدير النظام القانوني، ويُسجل كإجراء استثنائي."),
				frappe.PermissionError,
			)

	def on_trash(self):
		if self.docstatus == 1 and not is_system_admin():
			frappe.throw(
				_("لا يمكن حذف شكوى مقدمة إلا من مدير النظام القانوني."),
				frappe.PermissionError,
			)

	def _responsible_label(self):
		if self.jurisdiction_type == GRIEVANCE_PATH_LEGAL:
			return _("إدارة الشؤون القانونية")
		if self.jurisdiction_type == GRIEVANCE_PATH_COMMITTEE:
			return _("لجنة شكاوى الموظفين")
		return ""

	def _assert_submitted(self):
		if self.docstatus != 1:
			frappe.throw(_("يجب تقديم الشكوى أولًا."))
		if self.status in TERMINAL_STATUSES:
			frappe.throw(_("الشكوى مغلقة أو مرفوضة ولا تقبل إجراءات جديدة."))

	def _assert_path_role(self, include_members=False):
		roles = LEGAL_REVIEW_ROLES if self.jurisdiction_type == GRIEVANCE_PATH_LEGAL else (
			COMMITTEE_REVIEW_ROLES if include_members else COMMITTEE_WRITE_ROLES
		)
		require_roles(roles)

	def _add_action_log(
		self,
		action,
		previous_status,
		new_status,
		responsible_party=None,
		notes=None,
		request_reason=None,
		transfer_reason=None,
		original_jurisdiction=None,
		new_jurisdiction=None,
	):
		log = frappe.get_doc(
			{
				"doctype": "Grievance Action Log",
				"grievance": self.name,
				"action": action,
				"previous_status": previous_status,
				"new_status": new_status,
				"responsible_party": responsible_party or self._responsible_label(),
				"performed_by": frappe.session.user,
				"action_time": now_datetime(),
				"notes": notes,
				"request_reason": request_reason,
				"transfer_reason": transfer_reason,
				"original_jurisdiction": original_jurisdiction,
				"new_jurisdiction": new_jurisdiction,
				"is_system_generated": 1,
			}
		)
		log.insert(ignore_permissions=True)

	def _save_controlled(self, status, **updates):
		self.flags.grievance_controlled_update = True
		previous_status = self.status
		for fieldname, value in updates.items():
			self.set(fieldname, value)
		self.status = status
		self.save(ignore_permissions=True)
		return previous_status

	def _find_active_committee(self):
		rows = frappe.get_all(
			"Employee Complaints Committee",
			filters={
				"status": "Active",
				"start_date": ("<=", today()),
				"end_date": (">=", today()),
			},
			fields=["name", "start_date", "end_date"],
			order_by="start_date desc",
		)
		if len(rows) == 1:
			return rows[0].name
		if not rows:
			frappe.throw(_("لا توجد لجنة شكاوى موظفين نشطة حاليًا."))
		return None

	def _set_committee(self, committee=None):
		if self.jurisdiction_type != GRIEVANCE_PATH_COMMITTEE:
			return None
		committee = committee or self.committee or self._find_active_committee()
		if not committee:
			frappe.throw(
				_("يجب تحديد لجنة شكاوى الموظفين قبل قبول الشكوى في هذا المسار."),
			)
		status = frappe.db.get_value("Employee Complaints Committee", committee, "status")
		if status != "Active":
			frappe.throw(_("يجب اختيار لجنة شكاوى موظفين نشطة."))
		return committee

	@frappe.whitelist()
	def apply_grievance_action(self, action, notes=None, recommendation=None, committee=None):
		self.check_permission("read")
		self._assert_submitted()
		action = (action or "").strip()
		notes = (notes or "").strip()
		recommendation = (recommendation or "").strip()
		previous_status = self.status

		if action == "Accept":
			self._assert_path_role()
			updates = {"current_responsible": frappe.session.user}
			if self.jurisdiction_type == GRIEVANCE_PATH_COMMITTEE:
				updates["committee"] = self._set_committee(committee)
			previous = self._save_controlled(PATH_STATUS[self.jurisdiction_type], **updates)
			self._after_action(action, previous, notes)

		elif action == "Request Information":
			self._assert_path_role()
			if not notes:
				frappe.throw(_("يجب كتابة المطلوب من الموظف."))
			self.append(
				"clarifications",
				{
					"requested_on": now_datetime(),
					"requested_by": frappe.session.user,
					"request_text": notes,
					"status": "Requested",
				},
			)
			previous = self._save_controlled(
				"Awaiting Information",
				current_responsible=frappe.session.user,
			)
			self._after_action(action, previous, notes, request_reason=notes)

		elif action == "Resume Review":
			self._assert_path_role()
			previous = self._save_controlled(PATH_STATUS[self.jurisdiction_type])
			self._after_action(action, previous, notes)

		elif action == "Prepare Legal Recommendation":
			if self.jurisdiction_type != GRIEVANCE_PATH_LEGAL:
				frappe.throw(_("هذا الإجراء متاح لمسار الشؤون القانونية فقط."))
			require_roles(LEGAL_REVIEW_ROLES)
			if not recommendation:
				frappe.throw(_("نص التوصية القانونية مطلوب."))
			previous = self._save_controlled(
				"Legal Recommendation",
				recommendation=recommendation,
				recommendation_prepared_by=frappe.session.user,
				recommendation_date=today(),
				current_responsible=frappe.session.user,
			)
			self._after_action(action, previous, recommendation)

		elif action == "Prepare Committee Recommendation":
			if self.jurisdiction_type != GRIEVANCE_PATH_COMMITTEE:
				frappe.throw(_("هذا الإجراء متاح لمسار لجنة شكاوى الموظفين فقط."))
			require_roles(COMMITTEE_WRITE_ROLES)
			if not recommendation:
				frappe.throw(_("توصية اللجنة مطلوبة."))
			previous = self._save_controlled(
				"Committee Recommendation",
				recommendation=recommendation,
				recommendation_prepared_by=frappe.session.user,
				recommendation_date=today(),
				current_responsible=frappe.session.user,
			)
			self._after_action(action, previous, recommendation)

		elif action == "Schedule Committee Meeting":
			if self.jurisdiction_type != GRIEVANCE_PATH_COMMITTEE:
				frappe.throw(_("هذا الإجراء متاح لمسار لجنة شكاوى الموظفين فقط."))
			require_roles(COMMITTEE_WRITE_ROLES)
			previous = self._save_controlled(
				"Scheduled for Meeting",
				committee=self._set_committee(committee),
				current_responsible=frappe.session.user,
			)
			self._after_action(action, previous, notes)

		elif action == "Start Deliberation":
			if self.jurisdiction_type != GRIEVANCE_PATH_COMMITTEE:
				frappe.throw(_("هذا الإجراء متاح لمسار لجنة شكاوى الموظفين فقط."))
			require_roles(COMMITTEE_WRITE_ROLES)
			if not self.committee:
				frappe.throw(_("يجب تحديد اللجنة قبل بدء المدلولة."))
			previous = self._save_controlled(
				"Under Committee Deliberation",
				current_responsible=frappe.session.user,
			)
			self._after_action(action, previous, notes)

		elif action == "Refer for Decision":
			if self.jurisdiction_type == GRIEVANCE_PATH_LEGAL:
				require_roles(LEGAL_REVIEW_ROLES)
			else:
				require_roles(COMMITTEE_WRITE_ROLES)
			if not self.recommendation or not self.recommendation_prepared_by:
				frappe.throw(_("يجب إعداد التوصية قبل إحالة الشكوى للقرار."))
			previous = self._save_controlled(
				"Pending Decision",
				current_responsible=frappe.session.user,
			)
			self._after_action(action, previous, notes)

		elif action == "Close":
			require_roles(
				LEGAL_REVIEW_ROLES | COMMITTEE_WRITE_ROLES | {"Legal System Administrator"}
			)
			if self.status not in ("Decision Issued", "Rejected"):
				frappe.throw(_("لا يمكن إغلاق الشكوى قبل إصدار القرار أو الرفض."))
			settings = get_settings()
			if settings.get("grievance_close_requires_decision") and not self.decision_reference:
				frappe.throw(_("لا يمكن الإغلاق قبل تسجيل القرار المعتمد."))
			if not notes:
				frappe.throw(_("سبب الإغلاق مطلوب."))
			previous = self._save_controlled(
				"Closed",
				closure_date=today(),
				closure_reason=notes,
			)
			self._after_action(action, previous, notes)

		else:
			frappe.throw(_("إجراء الشكوى غير معروف: {0}").format(action))
		return {"name": self.name, "status": self.status}

	def _after_action(self, action, previous_status, notes=None, request_reason=None):
		self._add_action_log(
			action=action,
			previous_status=previous_status,
			new_status=self.status,
			notes=notes,
			request_reason=request_reason,
		)
		notify_grievance_transition(self)

	@frappe.whitelist()
	def provide_information(self, response_text, attachment=None):
		self.check_permission("read")
		self._assert_submitted()
		if self.status != "Awaiting Information":
			frappe.throw(_("لا توجد حاليًا معلومات مطلوبة من الموظف."))
		response_text = (response_text or "").strip()
		if not response_text:
			frappe.throw(_("نص الرد مطلوب."))
		user = frappe.session.user
		employee_user = get_grievance_employee_user(self)
		if not (is_system_admin() or user == employee_user or user == self.raised_by_user):
			frappe.throw(
				_("تقديم معلومات إضافية متاح للموظف صاحب الشكوى فقط."),
				frappe.PermissionError,
			)
		pending = None
		for row in self.clarifications:
			if row.status == "Requested":
				pending = row
				break
		if not pending:
			frappe.throw(_("لا يوجد طلب معلومات معلق لهذه الشكوى."))
		pending.response_text = response_text
		pending.responded_on = now_datetime()
		pending.responded_by = user
		pending.status = "Responded"
		if attachment:
			pending.attachment = attachment
		previous = self.status
		self.flags.grievance_controlled_update = True
		self.status = PATH_STATUS[self.jurisdiction_type]
		self.save(ignore_permissions=True)
		self._add_action_log(
			action="Provide Information",
			previous_status=previous,
			new_status=self.status,
			responsible_party=self._responsible_label(),
			notes=_("قدم الموظف معلومات إضافية."),
		)
		notify_grievance_transition(self, include_employee=False)
		return {"name": self.name, "status": self.status}

	@frappe.whitelist()
	def transfer_jurisdiction(self, new_jurisdiction, reason):
		self.check_permission("read")
		self._assert_submitted()
		new_jurisdiction = (new_jurisdiction or "").strip()
		reason = (reason or "").strip()
		if not is_system_admin():
			require_roles(
				{
					"Legal Grievance Manager",
					"Legal Department Manager",
					"Employee Complaints Committee Chair",
				}
			)
		if new_jurisdiction not in GRIEVANCE_PATHS:
			frappe.throw(_("جهة الاختصاص الجديدة غير صالحة."))
		if new_jurisdiction == self.jurisdiction_type:
			frappe.throw(_("الشكوى موجودة بالفعل لدى الجهة المحددة."))
		if not reason:
			frappe.throw(_("سبب التحويل مطلوب."))
		if self.status in ("Decision Issued", "Closed", "Rejected"):
			frappe.throw(_("لا يمكن تحويل شكوى صدر قرارها أو أغلقت."))

		old_jurisdiction = self.jurisdiction_type
		old_recommendation = self.recommendation or ""
		old_committee = self.committee
		original = self.original_jurisdiction or old_jurisdiction
		previous = self.status
		self.flags.grievance_controlled_update = True
		self.jurisdiction_type = new_jurisdiction
		self.original_jurisdiction = original
		self.transferred_on = now_datetime()
		self.transferred_by = frappe.session.user
		self.transfer_reason = reason
		self.status = "Submitted"
		self.current_responsible = None
		self.recommendation = None
		self.recommendation_prepared_by = None
		self.recommendation_date = None
		self.committee = None if new_jurisdiction == GRIEVANCE_PATH_LEGAL else old_committee
		self.save(ignore_permissions=True)
		note = _("تم التحويل من {0} إلى {1}. السبب: {2}").format(
			old_jurisdiction, new_jurisdiction, reason
		)
		if old_recommendation:
			note += "\n" + _("التوصية السابقة: {0}").format(old_recommendation)
		self._add_action_log(
			action="Transfer Jurisdiction",
			previous_status=previous,
			new_status="Submitted",
			transfer_reason=reason,
			original_jurisdiction=old_jurisdiction,
			new_jurisdiction=new_jurisdiction,
			notes=note,
		)
		notify_grievance_transition(self)
		return {"name": self.name, "status": self.status}

	@frappe.whitelist()
	def issue_decision(self, decision_text, external_reference=None):
		self.check_permission("read")
		self._assert_submitted()
		if self.status != "Pending Decision":
			frappe.throw(_("لا يمكن إصدار القرار في الحالة الحالية."))
		if not has_any_role({DECISION_ROLE, "Legal System Administrator"}):
			frappe.throw(
				_("إصدار القرار يتطلب دور المعتمد المخوّل."),
				frappe.PermissionError,
			)
		decision_text = (decision_text or "").strip()
		if not decision_text:
			frappe.throw(_("نص القرار مطلوب."))
		settings = get_settings()
		if settings.get("grievance_decision_separation_required"):
			if not self.recommendation_prepared_by:
				frappe.throw(_("لا يمكن إصدار القرار قبل توثيق معد التوصية."))
			if self.recommendation_prepared_by == frappe.session.user and not is_system_admin():
				frappe.throw(
					_("لا يجوز لمعد التوصية إصدار القرار بنفسه."),
					frappe.PermissionError,
				)

		decision_type = "Employee Legal Grievance"
		decision = frappe.get_doc(
			{
				"doctype": "Legal Decision",
				"decision_title": _("قرار بشأن الشكوى {0}").format(self.name),
				"decision_type": decision_type,
				"status": "Approved",
				"subject": self.grievance_title,
				"reference_doctype": self.doctype,
				"reference_name": self.name,
				"recommending_entity": self._responsible_label(),
				"recommendation": self.recommendation,
				"prepared_by": self.recommendation_prepared_by,
				"final_decision": decision_text,
				"decision_date": today(),
				"external_reference": external_reference,
				"decision_maker": frappe.session.user,
				"approved_on": now_datetime(),
				"recorded_by": frappe.session.user,
				"recorded_on": now_datetime(),
				"confidentiality": "Highly Confidential",
			}
		)
		decision.flags.decision_internal_approval = True
		decision.insert(ignore_permissions=True)

		previous = self.status
		self.flags.grievance_controlled_update = True
		self.approved_decision = decision_text
		self.decision_reference = decision.name
		self.decision_by = frappe.session.user
		self.decision_date = today()
		self.status = "Decision Issued"
		self.current_responsible = frappe.session.user
		self.save(ignore_permissions=True)
		self._add_action_log(
			action="Issue Decision",
			previous_status=previous,
			new_status=self.status,
			responsible_party=_("المعتمد المخوّل"),
			notes=_("تم تسجيل القرار {0}.").format(decision.name),
		)
		notify_grievance_transition(self)
		return {
			"name": self.name,
			"status": self.status,
			"decision": decision.name,
		}

	@frappe.whitelist()
	def get_available_grievance_actions(self):
		self.check_permission("read")
		if self.docstatus != 1 or self.status in TERMINAL_STATUSES:
			return []
		roles = set(frappe.get_roles(frappe.session.user))
		admin = is_system_admin()
		legal = bool(roles.intersection(LEGAL_REVIEW_ROLES))
		committee = bool(roles.intersection(COMMITTEE_WRITE_ROLES))
		actions = []

		def add(action, label, allowed):
			if allowed and action not in [item["action"] for item in actions]:
				actions.append({"action": action, "label": label})

		is_legal = self.jurisdiction_type == GRIEVANCE_PATH_LEGAL
		is_committee = self.jurisdiction_type == GRIEVANCE_PATH_COMMITTEE
		if self.status == "Submitted":
			add("Accept", _("قبول الشكوى وبدء المراجعة"), admin or (legal if is_legal else committee))
			add("Request Information", _("طلب معلومات من الموظف"), admin or (legal if is_legal else committee))
		elif self.status == "Awaiting Information":
			add("Request Information", _("طلب معلومات إضافية"), admin or (legal if is_legal else committee))
			add("Resume Review", _("استئناف المراجعة"), admin or (legal if is_legal else committee))
		elif self.status in ("Legal Review",):
			add("Prepare Legal Recommendation", _("إعداد التوصية القانونية"), admin or legal)
			add("Request Information", _("طلب معلومات من الموظف"), admin or legal)
		elif self.status in ("Committee Review", "Under Committee Deliberation"):
			add("Prepare Committee Recommendation", _("إعداد توصية اللجنة"), admin or committee)
			add("Schedule Committee Meeting", _("جدولة اجتماع اللجنة"), admin or committee)
			add("Request Information", _("طلب معلومات من الموظف"), admin or committee)
		elif self.status == "Scheduled for Meeting":
			add("Start Deliberation", _("بدء مداولات اللجنة"), admin or committee)
			add("Prepare Committee Recommendation", _("إعداد توصية اللجنة"), admin or committee)
			add("Request Information", _("طلب معلومات من الموظف"), admin or committee)
		elif self.status == "Legal Recommendation":
			add("Refer for Decision", _("إحالة الشكوى للقرار"), admin or legal)
			add("Request Information", _("طلب معلومات من الموظف"), admin or legal)
		elif self.status == "Committee Recommendation":
			add("Refer for Decision", _("إحالة الشكوى للقرار"), admin or committee)
			add("Schedule Committee Meeting", _("جدولة اجتماع اللجنة"), admin or committee)
			add("Request Information", _("طلب معلومات من الموظف"), admin or committee)
		elif self.status == "Pending Decision":
			add(
				"Issue Decision",
				_("إصدار القرار"),
				admin or DECISION_ROLE in roles,
			)
		if self.status in ("Decision Issued", "Rejected"):
			add("Close", _("إغلاق الشكوى"), admin or legal or committee)
		return actions
