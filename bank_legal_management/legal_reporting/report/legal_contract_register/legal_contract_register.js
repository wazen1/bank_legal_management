frappe.query_reports["Legal Contract Register"] = {
	filters: [
		{ fieldname: "from_date", label: __("نهاية العقد من"), fieldtype: "Date" },
		{ fieldname: "to_date", label: __("نهاية العقد إلى"), fieldtype: "Date" },
		{ fieldname: "status", label: __("الحالة"), fieldtype: "Select", options: ["", "Draft", "Under Legal Review", "Returned for Amendment", "Pending Approval", "Pending Signature", "Active", "Expiring", "Renewed", "Terminated", "Expired", "Archived"] },
		{ fieldname: "contract_type", label: __("نوع العقد"), fieldtype: "Select", options: ["", "Service", "Lease", "Consultancy", "Employment", "NDA", "Settlement", "Loan", "Procurement", "Other"] },
		{ fieldname: "company", label: __("الشركة"), fieldtype: "Link", options: "Company" },
	],
};
