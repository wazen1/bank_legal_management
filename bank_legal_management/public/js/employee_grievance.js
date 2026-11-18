frappe.ui.form.on("Employee Legal Grievance", {
	refresh(frm) {
		if (frm.is_new()) return;
		frm.add_custom_button(__("سجل الإجراءات"), () => {
			frappe.call({
				method: "bank_legal_management.api.get_grievance_timeline",
				args: { name: frm.doc.name },
				callback(r) {
					if (!r.message) return;
					const rows = (r.message.actions || [])
						.map(
							(a) =>
								`<tr><td>${frappe.utils.escape_html(a.action_time || "")}</td><td>${frappe.utils.escape_html(
									a.action
								)}</td><td>${frappe.utils.escape_html(a.new_status || "")}</td><td>${frappe.utils.escape_html(
									a.performed_by || ""
								)}</td></tr>`
						)
						.join("");
					frappe.msgprint({
						title: __("سجل الإجراءات"),
						message: `<table class="table table-bordered"><thead><tr><th>${__(
							"التاريخ"
						)}</th><th>${__("الإجراء")}</th><th>${__("الحالة")}</th><th>${__("المستخدم")}</th></tr></thead><tbody>${rows}</tbody></table>`,
						wide: true,
					});
				},
			});
		});

		frappe.call({
			method: "bank_legal_management.api.get_available_grievance_actions",
			args: { name: frm.doc.name },
			callback(r) {
				(r.message || []).forEach((item) => {
					frm.add_custom_button(item.label, () => run_action(frm, item.action));
				});
				if (frm.doc.status === "Awaiting Information") {
					const employeeUser = frm.doc.raised_by_user === frappe.session.user;
					if (employeeUser || frappe.user.has_role("Legal System Administrator")) {
						frm.add_custom_button(__("تقديم معلومات"), () => provide_information(frm));
					}
				}
				if (
					["Submitted", "Legal Review", "Committee Review", "Awaiting Information", "Legal Recommendation", "Committee Recommendation", "Scheduled for Meeting", "Under Committee Deliberation", "Pending Decision"].includes(
						frm.doc.status
					) &&
					(frappe.user.has_role("Legal Grievance Manager") ||
						frappe.user.has_role("Legal Department Manager") ||
						frappe.user.has_role("Employee Complaints Committee Chair") ||
						frappe.user.has_role("Legal System Administrator"))
				) {
					frm.add_custom_button(__("تحويل الاختصاص"), () => transfer_jurisdiction(frm));
				}
			},
		});
	},
});

function run_action(frm, action) {
	if (action === "Issue Decision") {
		frappe.prompt(
			[
				{ fieldname: "decision_text", label: __("نص القرار"), fieldtype: "Text", reqd: 1 },
				{ fieldname: "external_reference", label: __("المرجع الخارجي"), fieldtype: "Data" },
			],
			(values) => {
				frappe.call({
					method: "bank_legal_management.api.issue_grievance_decision",
					args: { name: frm.doc.name, ...values },
					freeze: true,
					callback: () => frm.reload_doc(),
				});
			},
			__("إصدار القرار")
		);
		return;
	}
	const fields = [];
	if (action === "Request Information" || action === "Close") {
		fields.push({
			fieldname: "notes",
			label: action === "Close" ? __("سبب الإغلاق") : __("المطلوب من الموظف"),
			fieldtype: "Text",
			reqd: 1,
		});
	} else {
		fields.push({ fieldname: "notes", label: __("ملاحظات"), fieldtype: "Text" });
	}
	if (action.includes("Recommendation")) {
		fields.push({
			fieldname: "recommendation",
			label: __("نص التوصية"),
			fieldtype: "Text",
			reqd: 1,
		});
	}
	if (action === "Accept" || action === "Schedule Committee Meeting") {
		fields.push({
			fieldname: "committee",
			label: __("لجنة شكاوى الموظفين"),
			fieldtype: "Link",
			options: "Employee Complaints Committee",
		});
	}
	frappe.prompt(
		fields,
		(values) => {
			frappe.call({
				method: "bank_legal_management.api.apply_grievance_action",
				args: { name: frm.doc.name, action, ...values },
				freeze: true,
				callback: () => frm.reload_doc(),
			});
		},
		__(action)
	);
}

function provide_information(frm) {
	frappe.prompt(
		[{ fieldname: "response_text", label: __("نص الرد"), fieldtype: "Text", reqd: 1 }],
		(values) => {
			frappe.call({
				method: "bank_legal_management.api.provide_grievance_information",
				args: { name: frm.doc.name, ...values },
				freeze: true,
				callback: () => frm.reload_doc(),
			});
		},
		__("تقديم معلومات")
	);
}

function transfer_jurisdiction(frm) {
	frappe.prompt(
		[
			{
				fieldname: "new_jurisdiction",
				label: __("جهة الاختصاص الجديدة"),
				fieldtype: "Select",
				options: ["Legal Department", "Employee Complaints Committee"],
				reqd: 1,
			},
			{ fieldname: "reason", label: __("سبب التحويل"), fieldtype: "Text", reqd: 1 },
		],
		(values) => {
			frappe.call({
				method: "bank_legal_management.api.transfer_grievance_jurisdiction",
				args: { name: frm.doc.name, ...values },
				freeze: true,
				callback: () => frm.reload_doc(),
			});
		},
		__("تحويل الاختصاص")
	);
}
