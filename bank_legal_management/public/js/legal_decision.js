frappe.ui.form.on("Legal Decision", {
	refresh(frm) {
		if (frm.is_new()) return;
		if (
			["Draft Recommendation", "Pending Approval"].includes(frm.doc.status) &&
			(frappe.user.has_role("Authorized Decision Maker") ||
				frappe.user.has_role("Legal System Administrator"))
		) {
			frm.add_custom_button(__("اعتماد القرار"), () => {
				frappe.prompt(
					[
						{ fieldname: "final_decision", label: __("النص النهائي للقرار"), fieldtype: "Text", reqd: 1 },
						{ fieldname: "external_reference", label: __("المرجع الخارجي"), fieldtype: "Data" },
					],
					(values) => {
						frm.set_value("final_decision", values.final_decision);
						frm.set_value("external_reference", values.external_reference);
						frm.set_value("decision_maker", frappe.session.user);
						frm.set_value("status", "Approved");
						frm.save();
					},
					__("اعتماد القرار")
				);
			});
			frm.add_custom_button(__("رفض القرار"), () => {
				frappe.prompt(
					[
						{ fieldname: "final_decision", label: __("النص النهائي"), fieldtype: "Text", reqd: 1 },
						{ fieldname: "rejection_reason", label: __("سبب الرفض"), fieldtype: "Text", reqd: 1 },
					],
					(values) => {
						frm.set_value("final_decision", values.final_decision);
						frm.set_value("rejection_reason", values.rejection_reason);
						frm.set_value("decision_maker", frappe.session.user);
						frm.set_value("status", "Rejected");
						frm.save();
					},
					__("رفض القرار")
				);
			});
		}
	},
});
