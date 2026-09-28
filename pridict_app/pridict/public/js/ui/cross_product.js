(() => {
	const namespace = (window.pridict = window.pridict || {});
	const DIALOG_TYPES = [
		["assign", ["assign", "assignment"]],
		["share", ["share"]],
		["email", ["email", "mail"]],
		["print", ["print", "pdf"]],
		["workflow", ["workflow", "approval", "reject"]],
		["import", ["import", "upload data"]],
		["export", ["export", "download data"]],
		["filter", ["filter"]],
		["upload", ["upload", "attach", "attachment"]],
		["confirm", ["confirm", "delete", "cancel document"]],
	];
	const EYEBROWS = {
		assign: "Ownership",
		share: "Access",
		email: "Communication",
		print: "Document output",
		workflow: "Approval workflow",
		import: "Data operation",
		export: "Data operation",
		filter: "View controls",
		upload: "Files",
		confirm: "Confirmation",
	};

	function classifyDialog(dialog) {
		const title = dialog.querySelector(".modal-title")?.textContent?.trim().toLowerCase() || "";
		const type = DIALOG_TYPES.find(([, terms]) => terms.some((term) => title.includes(term)))?.[0] || "general";
		dialog.classList.add("pridict-dialog");
		dialog.dataset.pridictDialog = type;

		const header = dialog.querySelector(".modal-header");
		const modalTitle = header?.querySelector(".modal-title");
		if (header && modalTitle && EYEBROWS[type] && !header.querySelector(".pridict-dialog-eyebrow")) {
			const eyebrow = document.createElement("span");
			eyebrow.className = "pridict-dialog-eyebrow";
			eyebrow.textContent = window.__ ? window.__(EYEBROWS[type]) : EYEBROWS[type];
			modalTitle.prepend(eyebrow);
		}
		return type;
	}

	function mark(selector, className) {
		document.querySelectorAll(selector).forEach((element) => element.classList.add(className));
	}

	function apply() {
		if (!window.location.pathname.startsWith("/app")) return;
		document.querySelectorAll(".modal").forEach(classifyDialog);
		mark(".notifications-list, .notification-list, .dropdown-notifications", "pridict-notification-surface");
		mark(".search-dialog, .search-results, .search-results-container", "pridict-search-surface");
		mark(".file-upload-area, .file-uploader, .file-upload", "pridict-upload-surface");
		mark(".msgprint-dialog, .toast-message, .alert", "pridict-message-surface");
		mark(".no-result, .no-results, .empty-state, .nothing-to-show", "pridict-empty-surface");
		mark(".freeze-message, .list-loading, .loading-text", "pridict-loading-surface");
		mark(".print-preview-wrapper, .print-toolbar", "pridict-output-surface");
	}

	let scheduled;
	function schedule() {
		window.clearTimeout(scheduled);
		scheduled = window.setTimeout(apply, 40);
	}

	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", apply, { once: true });
	} else {
		apply();
	}
	new MutationObserver(schedule).observe(document.documentElement, { childList: true, subtree: true });
	namespace.crossProduct = { apply, classifyDialog };
})();
