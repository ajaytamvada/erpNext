(() => {
	const namespace = (window.pridict = window.pridict || {});
	const surface = namespace.surface;
	if (!surface) return;

	function documentStatus(doc, fallbackFields = [], options = {}) {
		if (doc?.docstatus === 2 && options.cancelledFirst) return __("Cancelled");
		if (doc?.status) return options.translateStatus ? __(doc.status) : doc.status;
		for (const fieldname of fallbackFields) {
			if (doc?.[fieldname]) return doc[fieldname];
		}
		if (doc?.docstatus === 2 && options.cancelled !== false) return __("Cancelled");
		if (doc?.docstatus === 1) return __("Submitted");
		return __("Draft");
	}

	function ensureDocumentSummary(options) {
		const container = options.page.querySelector(options.containerSelector || ".form-layout,.layout-main-section");
		if (!container) return null;
		let block = options.page.querySelector(`.${options.className}`);
		if (!block) {
			block = document.createElement("section");
			block.className = `pridict-document-card ${options.className}`;
			container.prepend(block);
		} else {
			block.classList.add("pridict-document-card");
		}
		const fields = (options.fields || []).map(([label, value]) => `<article class="pridict-document-field"><span>${surface.escape(__(label))}</span><strong>${value}</strong></article>`).join("");
		const guidanceTone = options.guidanceTone ? ` data-tone="${surface.escape(options.guidanceTone)}"` : "";
		const guidanceClass = options.guidanceClass ? ` ${options.guidanceClass}` : "";
		const guidance = options.guidance ? `<p class="pridict-document-guidance${guidanceClass}"${guidanceTone}>${surface.escape(__(options.guidance))}</p>` : "";
		const headerClass = options.headerClass ? ` ${options.headerClass}` : "";
		const fieldsClass = options.fieldsClass ? ` ${options.fieldsClass}` : "";
		const emptyName = __(options.emptyName || "New document");
		const fieldGrid = options.fields?.length ? `<div class="pridict-document-fields${fieldsClass}">${fields}</div>` : "";
		const content = options.guidancePosition === "before-fields" ? `${guidance}${fieldGrid}` : `${fieldGrid}${guidance}`;
		const markup = `<header class="pridict-document-card-header${headerClass}"><div><span>${surface.escape(__(options.eyebrow))}</span><strong>${surface.escape(options.name || emptyName)}</strong></div><b class="pridict-document-status">${surface.escape(options.status)}</b></header>${content}`;
		surface.render(block, markup);
		return block;
	}

	function safeDocumentFields(doc, fieldnames, labelResolver) {
		return fieldnames.map((fieldname) => {
			const label = labelResolver ? labelResolver(fieldname) : fieldname.replaceAll("_", " ");
			return [label, surface.escape(doc?.[fieldname] ?? __("Not set"))];
		});
	}

	function tagNativeFieldSections(page, fieldnames, sharedClass, moduleClass) {
		const sections = [];
		for (const fieldname of fieldnames) {
			const section = page.querySelector(`[data-fieldname="${fieldname}"]`)?.closest(".form-section");
			if (!section) continue;
			if (sharedClass) section.classList.add(sharedClass);
			if (moduleClass) section.classList.add(moduleClass);
			if (!sections.includes(section)) sections.push(section);
		}
		return sections;
	}

	function tagNativeFieldSection(page, fieldnames, sharedClass, moduleClass) {
		return tagNativeFieldSections(page, fieldnames, sharedClass, moduleClass)[0] || null;
	}

	function ensureGridScrollNote(section, message, className = "pridict-grid-scroll-note") {
		if (!section) return null;
		let note = section.querySelector(`.${className}`);
		if (!note) {
			note = document.createElement("p");
			note.className = className;
			section.prepend(note);
		}
		note.textContent = __(message);
		return note;
	}

	function tagNativeDocumentRegions(page, classes = {}) {
		page.querySelectorAll(".form-grid").forEach((element) => {
			element.classList.add("pridict-native-grid");
			if (classes.grid) element.classList.add(classes.grid);
		});
		const timeline = page.querySelector(".timeline");
		if (timeline) {
			timeline.classList.add("pridict-native-timeline");
			if (classes.timeline) timeline.classList.add(classes.timeline);
		}
		const linkedSelectors = [".form-dashboard", ".form-links", ".document-link-badge", ...(classes.linkedSelectors || [])].join(",");
		page.querySelectorAll(linkedSelectors).forEach((element) => {
			element.classList.add("pridict-native-linked-documents");
			if (classes.linked) element.classList.add(classes.linked);
		});
	}

	namespace.components = { documentStatus, ensureDocumentSummary, ensureGridScrollNote, safeDocumentFields, tagNativeDocumentRegions, tagNativeFieldSection, tagNativeFieldSections };
})();
