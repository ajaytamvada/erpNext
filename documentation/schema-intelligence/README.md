# Schema Intelligence examples

These files were generated on 22 September 2026 from the disposable local Frappe/ERPNext sites used
for Milestone 1 integration verification.

- `examples/sales-order-schema.json`: normalized Sales Order schema and its outbound relationships
  from the clean-site snapshot.
- `examples/sales-order-relationships.mmd`: Mermaid graph generated only from extracted Sales Order
  relationships.
- `examples/controlled-customization-diff.json`: structural comparison created by adding the validated
  `Customer.custom_pridict_schema_tier` Custom Field and changing the effective label of
  `Customer.customer_name` through a Property Setter on the customized disposable site.

The customization fixture was removed after capture. These artifacts contain schema metadata, not
business records or credentials.
