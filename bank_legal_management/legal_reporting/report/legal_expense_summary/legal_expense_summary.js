frappe.query_reports["Legal Expense Summary"] = {
	filters: [
		{ fieldname: "from_date", label: __("من تاريخ"), fieldtype: "Date" },
		{ fieldname: "to_date", label: __("إلى تاريخ"), fieldtype: "Date" },
		{ fieldname: "status", label: __("الحالة"), fieldtype: "Select", options: ["", "Draft", "Pending Review", "Approved", "Rejected", "Paid", "Cancelled"] },
		{ fieldname: "expense_type", label: __("نوع المصروف"), fieldtype: "Select", options: ["", "Legal Fees", "Court Fees", "Translation", "Expert Fees", "Travel", "Other"] },
		{ fieldname: "company", label: __("الشركة"), fieldtype: "Link", options: "Company" },
	],
};
