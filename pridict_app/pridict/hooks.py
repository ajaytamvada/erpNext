app_name = "pridict"
app_title = "Pridict"
app_publisher = "RiditStack"
app_description = "Pridict branding and Enterprise UI for ERPNext"
app_license = "GNU General Public License (v3)"
app_logo_url = "/assets/pridict/images/pridict-wordmark.svg"
brand_html = '<img src="/assets/pridict/images/pridict-wordmark.svg" alt="Pridict">'

website_context = {
	"favicon": "/assets/pridict/images/pridict-icon.svg",
	"splash_image": "/assets/pridict/images/pridict-icon.svg",
}

required_apps = ["erpnext"]

app_include_css = "pridict.bundle.css"
app_include_js = "pridict.bundle.js"
web_include_css = "pridict.bundle.css"
web_include_js = "pridict.bundle.js"

welcome_email = "pridict.email.get_welcome_email_subject"

after_install = "pridict.setup.install.apply_pridict_setup"
after_migrate = "pridict.setup.install.apply_pridict_setup"

scheduler_events = {
	"hourly": ["pridict.schema_intelligence.scheduler.hourly"],
}

notification_skip_email_types = ["Schema Intelligence"]
