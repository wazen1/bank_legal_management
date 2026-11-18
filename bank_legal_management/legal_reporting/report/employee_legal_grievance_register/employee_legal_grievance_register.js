frappe.query_reports["Employee Legal Grievance Register"] = {
	filters: [
		{ fieldname: "from_date", label: __("من تاريخ"), fieldtype: "Date" },
		{ fieldname: "to_date", label: __("إلى تاريخ"), fieldtype: "Date" },
		{ fieldname: "status", label: __("الحالة"), fieldtype: "Select", options: ["", "Submitted", "Legal Review", "Committee Review", "Awaiting Information", "Legal Recommendation", "Committee Recommendation", "Scheduled for Meeting", "Under Committee Deliberation", "Pending Decision", "Decision Issued", "Closed", "Rejected"] },
		{ fieldname: "jurisdiction_type", label: __("جهة الاختصاص"), fieldtype: "Select", options: ["", "Legal Department", "Employee Complaints Committee"] },
		{ fieldname: "grievance_type", label: __("نوع الشكوى"), fieldtype: "Select", options: ["", "Workplace", "Discrimination", "Harassment", "Financial", "Administrative", "Contractual", "Retaliation", "Other"] },
		{ fieldname: "employee", label: __("الموظف"), fieldtype: "Link", options: "Employee" },
		{ fieldname: "importance", label: __("الأهمية"), fieldtype: "Select", options: ["", "Low", "Medium", "High", "Critical"] },
	],
};
