frappe.ui.form.on("Legal Expense", {
	refresh(frm) {
		if (frm.is_new()) return;
		if (frm.doc.status === "Draft") {
			frm.add_custom_button(__("إرسال للمراجعة"), () => call(frm, "submit_expense_for_review"));
		}
		if (frm.doc.status === "Pending Review" && can_approve()) {
			frm.add_custom_button(__("اعتماد"), () => call(frm, "approve_legal_expense"));
			frm.add_custom_button(__("رفض"), () =>
				frappe.prompt(
					[{ fieldname: "rejection_reason", label: __("سبب الرفض"), fieldtype: "Text", reqd: 1 }],
					(values) =>
						call(frm, "reject_legal_expense", values),
					__("رفض المصروف")
				)
			);
		}
		if (frm.doc.status === "Approved") {
			frm.add_custom_button(__("تعليم كمدفوع"), () => call(frm, "mark_legal_expense_paid"));
			if (can_approve()) {
				frm.add_custom_button(__("رفض"), () =>
					frappe.prompt(
						[{ fieldname: "rejection_reason", label: __("سبب الرفض"), fieldtype: "Text", reqd: 1 }],
						(values) => call(frm, "reject_legal_expense", values),
						__("رفض المصروف")
					)
				);
			}
		}
		if (["Draft", "Pending Review"].includes(frm.doc.status)) {
			frm.add_custom_button(__("إلغاء"), () => call(frm, "cancel_legal_expense"));
		}
	},
});

function can_approve() {
	return (
		frappe.user.has_role("Legal Department Manager") ||
		frappe.user.has_role("Legal System Administrator")
	);
}

function call(frm, method, args) {
	frappe.call({
		method: `bank_legal_management.api.${method}`,
		args: { name: frm.doc.name, ...(args || {}) },
		freeze: true,
		callback: () => frm.reload_doc(),
	});
}
