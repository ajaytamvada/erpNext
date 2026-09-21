# Pridict documentation

Prepared 17 September 2026. Audience: a trading/distribution business holding inventory.

## Start here

1. Read the [functional user guide](FUNCTIONAL-GUIDE.md), especially sections 2–5. It explains setup and your first purchase without assuming ERP experience.
2. Complete the [practice workbook](PRACTICE-WORKBOOK.md) in a designated test company/site. It follows the same stock through purchase, sale and payment and gives expected results.
3. Use the [technical guide](TECHNICAL-GUIDE.md) for architecture, deployment, access, backups, troubleshooting and maintenance.

**Your immediate question:** Yes. Open a submitted **Material Request** with **Purpose = Purchase**, then choose **Create → Purchase Order**. There must be an unordered quantity remaining and your user must have permission. Review the supplier, quantities, prices, warehouse and taxes before submitting the resulting order. Section 5 of the functional guide explains every step and common missing-button cases.

## What these guides describe

These guides describe Pridict's ERPNext v15 business functionality and the deployment recorded in this repository. The latest implementation checkpoint records Frappe 15.120.1, ERPNext 15.121.2 and Pridict 0.1.0. The production-style UI redesign is in progress; an approved mockup is not proof that a screen or feature is deployed.

Use the global search to find document names such as **Material Request**, **Purchase Order** and **Stock Balance**. Sidebar labels, layout and button placement may change during the redesign; the document relationships remain the same.

This documentation task inspected source and project records; it did not log in to UAT, create transactions, run a new restore drill, or change infrastructure. Standard workflows are instructions to validate with your configured roles, settings and accounting policies, not a claim that every flow has passed live acceptance testing.

## Document ownership and updates

| Document | Owner | Update when |
|---|---|---|
| Functional guide | Product owner + operations/accounting leads | Screens, business policy, permissions or workflows change |
| Practice workbook | QA + business process owners | A release changes transaction behavior or reporting |
| Technical guide | Application/platform maintainer | Versions, infrastructure, release process or integrations change |

Store release-specific screenshots and test results alongside the release evidence. Review these guides after the current CLI implementation finishes. These files can become help-center content later, but no public help URLs or in-product links have been configured by creating them.
