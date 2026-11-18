frappe.ui.form.on("Employee Complaints Committee Meeting", {
	refresh(frm) {
		if (frm.is_new()) return;
		if (frm.doc.status === "Completed" && frm.doc.minutes_status !== "Approved") {
			if (
				frappe.user.has_role("Employee Complaints Committee Chair") ||
				frappe.user.has_role("Legal System Administrator")
			) {
				frm.add_custom_button(__("اعتماد المحضر"), () => {
					frappe.call({
						method: "bank_legal_management.api.approve_committee_minutes",
						args: { name: frm.doc.name },
						freeze: true,
						callback: () => frm.reload_doc(),
					});
				});
			}
		}
	},
});
