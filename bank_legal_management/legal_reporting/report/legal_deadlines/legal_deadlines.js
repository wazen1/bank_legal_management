frappe.query_reports["Legal Deadlines"] = {
	filters: [
		{ fieldname: "from_date", label: __("من تاريخ"), fieldtype: "Date", default: frappe.datetime.get_today() },
		{ fieldname: "to_date", label: __("إلى تاريخ"), fieldtype: "Date", default: frappe.datetime.add_days(frappe.datetime.get_today(), 60) },
		{ fieldname: "deadline_type", label: __("نوع الاستحقاق"), fieldtype: "Select", options: ["", "جلسة", "انتهاء عقد", "التزام تعاقدي", "طلب رأي", "اجتماع لجنة", "متابعة مراسلة", "انتهاء مستند"] },
	],
};
