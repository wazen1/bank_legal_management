frappe.ui.form.on("Legal Contract", {
	refresh(frm) {
		if (frm.is_new()) return;
		frm.add_custom_button(__("ملخص الالتزامات"), () => {
			frm.call("get_contract_summary").then((r) => {
				if (!r.message) return;
				const rows = (r.message.obligations || [])
					.map(
						(o) =>
							`<tr><td>${frappe.utils.escape_html(o.description || "")}</td><td>${frappe.utils.escape_html(
								o.next_due_date || o.due_date || ""
							)}</td><td>${frappe.utils.escape_html(o.status || "")}</td></tr>`
					)
					.join("");
				frappe.msgprint({
					title: __("ملخص الالتزامات"),
					message: `<table class="table table-bordered"><thead><tr><th>${__("الالتزام")}</th><th>${__(
						"الاستحقاق"
					)}</th><th>${__("الحالة")}</th></tr></thead><tbody>${rows}</tbody></table>`,
					wide: true,
				});
			});
		});
	},
});
