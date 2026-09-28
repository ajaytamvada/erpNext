(() => {
	const namespace = (window.pridict = window.pridict || {});
	const routes = namespace.routeContext;
	const surface = namespace.surface;
	const components = namespace.components;
	if (!routes || !surface || !components) return;

	const administration = {
		User: ["User account", "Manage access state and account classification without exposing credentials.", ["full_name", "email", "enabled", "user_type", "last_active"]],
		Role: ["Role", "Maintain role identity and Desk access while preserving native permission behavior.", ["role_name", "desk_access", "disabled"]],
		"Role Profile": ["Role profile", "Group native roles for repeatable user assignment.", ["role_profile", "disabled"]],
		"User Permission": ["User permission", "Limit records through native user-permission rules.", ["user", "allow", "for_value", "applicable_for"]],
		Workflow: ["Workflow", "Configure approval states and transitions without changing document controllers.", ["workflow_name", "document_type", "is_active", "override_status"]],
		"Workflow State": ["Workflow state", "Maintain reusable workflow labels and presentation.", ["workflow_state_name", "icon", "style"]],
		Notification: ["Notification", "Configure native document and schedule notifications.", ["subject", "document_type", "channel", "enabled"]],
		"Email Account": ["Email account", "Review account purpose and enabled directions; credentials remain in native protected controls.", ["email_account_name", "email_id", "enable_incoming", "enable_outgoing", "default_incoming", "default_outgoing"]],
		"Email Template": ["Email template", "Maintain reusable subject and message content.", ["name", "subject", "use_html"]],
		"Auto Email Report": ["Scheduled report", "Manage scheduled report delivery and frequency.", ["report", "enabled", "frequency", "format"]],
		"Data Import": ["Data import", "Use native validation, preview, import, and error handling.", ["reference_doctype", "import_type", "status"]],
		"Data Export": ["Data export", "Select fields and filters using the native export tool.", ["reference_doctype"]],
		"Print Format": ["Print format", "Maintain document print presentation and format type.", ["name", "doc_type", "print_format_type", "disabled"]],
		"Print Settings": ["Print settings", "Configure shared print behavior without changing transaction data.", ["with_letterhead", "repeat_header_footer", "allow_print_for_draft", "allow_print_for_cancelled"]],
		"System Settings": ["System settings", "Manage site-wide locale, session, security, and display settings in native sections.", ["country", "language", "time_zone", "date_format", "time_format"]],
		"Global Defaults": ["Global defaults", "Maintain company, currency, and country defaults.", ["default_company", "current_fiscal_year", "country", "default_currency"]],
		"Website Settings": ["Website settings", "Maintain site identity, navigation, footer, and public behavior.", ["app_name", "home_page", "disable_signup", "hide_footer_signup"]],
		Employee: ["Employee", "Maintain the core employee identity used by assignments and transactions; HRMS workflows are not installed.", ["employee_name", "company", "department", "designation", "status"]],
	};
	const integrations = {
		Webhook: ["Webhook", "Configure event delivery while keeping endpoints, headers, and secrets in native protected controls.", ["webhook_doctype", "webhook_docevent", "request_structure", "enabled"]],
		"Social Login Key": ["Social login", "Configure provider identity and login availability without surfacing client secrets.", ["provider_name", "enable_social_login", "base_url"]],
		"LDAP Settings": ["LDAP", "Configure directory authentication in the native protected form.", ["enabled", "ldap_email_field", "ldap_username_field"]],
		"OAuth Client": ["OAuth client", "Manage registered applications, scopes, and redirect behavior without exposing secrets in the summary.", ["app_name", "scopes", "default_redirect_uri"]],
		"OAuth Provider Settings": ["OAuth provider", "Manage provider behavior using native secure controls.", ["skip_authorization", "lifespan"]],
		"SMS Settings": ["SMS", "Configure the selected SMS gateway and parameters in the native form.", ["use_post", "receiver_parameter"]],
		"Slack Webhook URL": ["Slack webhook", "Maintain document-event delivery without displaying webhook URLs in the summary.", ["webhook_name", "show_document_link"]],
		"Google Settings": ["Google settings", "Manage Google API enablement and authorization through native controls.", ["enable", "app_name"]],
		"Google Contacts": ["Google contacts", "Configure contact synchronization direction and account ownership.", ["user", "enable"]],
		"Google Calendar": ["Google calendar", "Configure calendar synchronization without exposing authorization data.", ["calendar_name", "user", "enable", "pull_from_google", "push_to_google"]],
		"Google Drive": ["Google Drive", "Configure backup or file integration through native authorization controls.", ["enable"]],
		"Dropbox Settings": ["Dropbox", "Configure backup behavior without exposing access credentials.", ["enabled", "frequency"]],
		"S3 Backup Settings": ["S3 backup", "Configure storage and backup schedules without exposing secret keys.", ["enabled", "frequency"]],
		"Plaid Settings": ["Plaid", "Configure banking integration through native protected settings.", ["enabled"]],
	};
	const journeys = {
		administration: [["Administration", "pridict-administration"], ["Users", "user", "User"], ["Roles", "role", "Role"], ["Workflows", "workflow", "Workflow"], ["Notifications", "notification", "Notification"], ["Imports", "data-import", "Data Import"], ["Print", "print-format", "Print Format"], ["Settings", "erpnext-settings"]],
		integrations: [["Integrations", "pridict-integrations"], ["Webhooks", "webhook", "Webhook"], ["OAuth", "oauth-client", "OAuth Client"], ["Social login", "social-login-key", "Social Login Key"], ["Google", "google-settings", "Google Settings"], ["Backups", "s3-backup-settings", "S3 Backup Settings"], ["Compatibility", "erpnext-integrations"]],
	};

	function fieldLabel(doctype, fieldname) {
		return frappe.meta.get_docfield(doctype, fieldname)?.label || fieldname.replaceAll("_", " ");
	}

	function apply(context) {
		const module = context.isAdministration ? "administration" : context.isIntegrations ? "integrations" : null;
		if (!module) {
			surface.remove(".pridict-admin-journey,.pridict-admin-intro,.pridict-admin-summary");
			return;
		}
		const page = surface.visiblePage();
		if (!page) return;
		const journey = journeys[module];
		const nav = surface.ensureJourney(page, { className: "pridict-admin-journey", label: `${module} navigation`, items: journey });
		nav.querySelectorAll("button").forEach((button, index) => {
			const active = (journey[index][2] || journey[index][0]) === context.doctype || button.dataset.route === context.slug;
			button.classList.toggle("is-active", active);
		});
		const config = (module === "administration" ? administration : integrations)[context.doctype];
		if (!config) return;
		if (context.surface === "list") {
			surface.ensureIntro(page, "pridict-admin-intro", module === "administration" ? "System administration" : "Connected services", context.doctype, config[1]);
		}
		if (context.surface === "form" && window.cur_frm?.doc?.doctype === context.doctype) {
			const doc = window.cur_frm.doc;
			const state = doc.enabled === 0 || doc.disabled === 1 ? __("Disabled") : doc.enabled === 1 ? __("Enabled") : __("Configured");
			components.ensureDocumentSummary({
				page,
				className: "pridict-admin-summary",
				eyebrow: config[0],
				emptyName: "New configuration",
				name: doc.name,
				status: state,
				fields: components.safeDocumentFields(doc, config[2], (field) => fieldLabel(context.doctype, field)),
				guidance: config[1],
				guidancePosition: "before-fields",
			});
			components.tagNativeDocumentRegions(page, { grid: "pridict-admin-grid" });
		}
	}

	function refreshForm() {
		setTimeout(() => apply(routes.classify()), 60);
		setTimeout(() => apply(routes.classify()), 260);
	}

	[...Object.keys(administration), ...Object.keys(integrations)].forEach((doctype) => {
		frappe.ui.form.on(doctype, { refresh: refreshForm, onload_post_render: refreshForm });
	});
	const refresh = routes.onRouteChange((context) => {
		setTimeout(() => apply(context), 120);
		setTimeout(() => apply(context), 500);
	});
	const observer = new MutationObserver(() => refresh());
	observer.observe(document.documentElement, { childList: true, subtree: true });
	window.setTimeout(() => observer.disconnect(), 20000);
	namespace.administrationIntegrations = { apply, refreshForm };
})();
