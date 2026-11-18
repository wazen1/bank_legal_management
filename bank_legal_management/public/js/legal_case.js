frappe.ui.form.on("Legal Case", {
	refresh(frm) {
		if (frm.is_new()) return;
		frm.add_custom_button(__("ملخص القضية"), () => {
			frappe.call({
				method: "frappe.client.get",
				args: { doctype: "Legal Case", name: frm.doc.name },
				callback() {
					frm.call("get_case_summary").then((r) => {
						if (!r.message) return;
						frappe.msgprint({
							title: __("ملخص القضية"),
							message: `${__("الحالة")}: ${frappe.utils.escape_html(r.message.status)}<br>${__(
								"الجلسة القادمة"
							)}: ${frappe.utils.escape_html(r.message.next_hearing_date || "-")}<br>${__(
								"آخر جلسة"
							)}: ${frappe.utils.escape_html(r.message.last_hearing_date || "-")}`,
						});
					});
				},
			});
		});
	},
});
