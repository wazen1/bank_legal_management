frappe.ui.form.on("Legal Opinion Request", {
	refresh(frm) {
		if (frm.is_new()) return;
		if (frm.doc.status === "Under Review" && can_review()) {
			frm.add_custom_button(__("طلب توضيح"), () =>
				frappe.prompt(
					[{ fieldname: "clarification_request", label: __("نص طلب التوضيح"), fieldtype: "Text", reqd: 1 }],
					(values) =>
						api(frm, "request_opinion_clarification", values),
					__("طلب توضيح")
				)
			);
		}
		if (
			frm.doc.status === "Awaiting Clarification" &&
			(frm.doc.requested_by === frappe.session.user ||
				frappe.user.has_role("Legal System Administrator"))
		) {
			frm.add_custom_button(__("تقديم التوضيح"), () =>
				frappe.prompt(
					[{ fieldname: "clarification_response", label: __("نص التوضيح"), fieldtype: "Text", reqd: 1 }],
					(values) =>
						api(frm, "provide_opinion_clarification", values),
					__("تقديم التوضيح")
				)
			);
		}
	},
});

function can_review() {
	return (
		frappe.user.has_role("Legal Opinion Officer") ||
		frappe.user.has_role("Legal Officer") ||
		frappe.user.has_role("Legal Department Manager") ||
		frappe.user.has_role("Legal System Administrator")
	);
}

function api(frm, method, args) {
	frappe.call({
		method: `bank_legal_management.api.${method}`,
		args: { name: frm.doc.name, ...args },
		freeze: true,
		callback: () => frm.reload_doc(),
	});
}
