frappe.query_reports["Legal Case Register"] = {
	filters: [
		{ fieldname: "from_date", label: __("من تاريخ"), fieldtype: "Date" },
		{ fieldname: "to_date", label: __("إلى تاريخ"), fieldtype: "Date" },
		{ fieldname: "status", label: __("الحالة"), fieldtype: "Select", options: ["", "Draft", "Registered", "Under Review", "Assigned", "In Progress", "Hearing Scheduled", "Awaiting Documents", "Awaiting Judgment", "Judgment Issued", "Under Appeal", "Settled", "Closed", "Archived"] },
		{ fieldname: "case_type", label: __("نوع القضية"), fieldtype: "Select", options: ["", "Civil", "Commercial", "Labor", "Criminal", "Administrative", "Banking", "Execution", "Other"] },
		{ fieldname: "company", label: __("الشركة"), fieldtype: "Link", options: "Company" },
	],
};
