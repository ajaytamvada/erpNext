# Pridict functional user guide

Version 1.0 — 17 September 2026. For trading and distribution with inventory.

## Contents

1. How the product fits together
2. First login and navigation
3. Set up your business in the right order
4. Document states and responsibility
5. Purchase stock: Material Request through supplier payment
6. Inventory operations
7. Sell stock and collect payment
8. Returns, corrections and exceptional cases
9. Accounting and management reports
10. Roles, approvals and customer access
11. Daily operating routine
12. Troubleshooting and glossary
13. Sources and scope

## 1. How the product fits together

Pridict is your branded application built on ERPNext and the Frappe framework. Its business records connect purchasing, warehouse operations, sales and accounting. You normally create the next document **from the previous one**, preserving quantities and references, rather than typing the same transaction again.

| Business question | Document or area |
|---|---|
| What do we need to buy? | Material Request |
| What did a vendor quote? | Supplier Quotation; optionally preceded by Request for Quotation |
| What did we order? | Purchase Order |
| What arrived in the warehouse? | Purchase Receipt |
| What does the vendor bill us? | Purchase Invoice |
| What did we pay? | Payment Entry, type Pay |
| What did we offer a customer? | Quotation |
| What did the customer order? | Sales Order |
| What did we ship? | Delivery Note |
| What did we bill? | Sales Invoice |
| What did the customer pay? | Payment Entry, type Receive |

The normal stock purchase path is:

**Material Request → Purchase Order → Purchase Receipt → Purchase Invoice → Payment Entry**

The normal stock sale path is:

**Quotation → Sales Order → Delivery Note → Sales Invoice → Payment Entry**

Quotation and request steps can be optional depending on business policy. Buying/Selling Settings can require certain preceding documents. A dashboard shows summaries; the linked documents and ledgers provide the detailed evidence.

## 2. First login and navigation

Open the recorded UAT address: https://pridict-demo.centralindia.cloudapp.azure.com. Use the credentials supplied privately. The demo's recorded running hours are 07:00–23:00 India time; contact the administrator if it is unavailable outside that window.

1. Log in and confirm your name and company context. Ask your administrator which company is designated for practice.
2. If the setup wizard appears, complete it with approved company information. If it does not appear, inspect existing masters before creating duplicates.
3. Use global search to open **Company**, **Item**, **Material Request**, or another exact document name.
4. A **list** shows many records. Filters narrow the list; open a row to view its **form**.
5. A form can contain tabs, an Items table, totals, attachments, comments and linked-document information. Open an item row to see fields hidden from the compact table.
6. **New/Add** creates a draft. **Save** stores it. **Submit** finalizes a submittable transaction, subject to permission and workflow.
7. **Create** on a submitted record often offers the next transaction. **Get Items From** on a draft can fetch an eligible source document.
8. Use document links/connections to navigate back to the request, order, receipt or invoice. Inspect those links when reconciling quantities.

Do not assume all users see the same menus. Visibility depends on roles, permissions, enabled features and document state. Changing the theme changes appearance, not financial behavior.

## 3. Set up your business in the right order

Complete this once with your administrator and accountant. Existing UAT companies may already contain test data; this is not an instruction to rerun setup over them.

### 3.1 Company and accounting foundation

Search **Company**. Confirm legal name, abbreviation, country, base currency and chart of accounts. Select the correct company consistently on transactions. Set up the fiscal year and accounting periods appropriate to the business.

Have the accountant confirm default receivable/payable accounts, stock and stock-received-but-not-billed accounts where applicable, income/expense accounts, bank/cash accounts and cost centers. A cost center categorizes financial activity; it is not a warehouse.

For Indian operations, confirm the installed localization capabilities and approved tax setup before issuing real invoices. This guide does not establish GST compliance or assume an additional compliance app is installed. Have the accountant validate tax templates, tax identifiers, numbering and statutory output.

### 3.2 Warehouses

Search **Warehouse** and review the company-specific tree. Use transaction warehouses, not a group node, on stock movements. Example operational names:

- Main Stores: saleable stock received from suppliers.
- Dispatch: stock staged for shipment, if your process needs a separate location.
- Rejected/Quarantine: physically received goods awaiting a decision.

Create locations only when you will maintain their balances accurately. A warehouse belongs to a company; do not mix companies accidentally. Warehouse abbreviations may appear in displayed names.

### 3.3 Items and units

Search **Item**. For a traded physical product, enter a stable Item Code, name, Item Group, Stock UOM and enable **Maintain Stock**. Set company-specific defaults such as warehouse and relevant accounts where appropriate.

Example: `DEMO-CABLE`, Network Cable, Stock UOM `Nos`. If purchased in boxes of ten, define the purchase UOM conversion correctly: one box equals ten stock units. Test conversion before real transactions; a conversion error affects stock and prices.

Use non-stock items for services where no inventory should be maintained. Configure serial or batch tracking before transacting when required; these choices have consequences once stock exists. ERPNext v15 may use Serial and Batch Bundles in stock transactions; involve the stock administrator for setup.

### 3.4 Suppliers and customers

Create **Supplier** records with the correct group, currency, address/contact and payment terms. A default supplier can be assigned to an item's company defaults, but a general item need not be restricted to one supplier.

Create **Customer** records with group, territory, address/contact, currency and payment terms. Confirm that invoices go to the correct legal entity. A contact email alone does not create a portal login or grant document access.

### 3.5 Prices, taxes and terms

Use **Price List** and **Item Price** for standard buying and selling prices. Confirm currency, UOM and applicable dates. A price not appearing on an order can indicate a missing matching price, not a broken item.

Configure Purchase/Sales Taxes and Charges Templates and payment terms with the accountant. Review taxes and totals on each document; a copied template may not suit every transaction. Configure letterhead and print formats separately from the application's Pridict logo.

### 3.6 Business settings

Review **Buying Settings**, **Selling Settings**, **Stock Settings** and **Accounts Settings** with the process owners. Decide whether receipts require purchase orders, invoices require receipts, delivery documents are required, negative stock is allowed, and who can backdate or submit records. Record these decisions before user training.

### 3.7 Opening data

Choose an agreed go-live cutoff date. Prepare opening stock quantities and valuation by warehouse, outstanding customer/supplier invoices, bank balances and other opening balances. Import masters before transactions and validate a small sample first.

Use the appropriate opening tools with your accountant; **Stock Reconciliation** can establish opening stock where applicable. Do not record the same opening inventory through both an opening stock entry and a purchase receipt. Reconcile stock valuation and the accounting opening balances before go-live.

### Setup completion check

Before the first practice purchase, you should have one test company, a usable warehouse, one stock item, one supplier, one customer, correct accounts, and users with buying/stock/accounts/selling access as needed. The [practice workbook](PRACTICE-WORKBOOK.md) provides a controlled exercise.

## 4. Document states and responsibility

| State | Meaning | What to do |
|---|---|---|
| Draft | Saved but not finalized | Review fields, quantities, rates and links |
| Submitted | Finalized business transaction | Create the next document or follow the controlled correction process |
| Cancelled | Submitted transaction was cancelled | Inspect linked documents and reversal effects; amend only when appropriate |
| Workflow state | Organization-defined approval step | Follow assigned approver actions; it is separate from ordinary status labels |

Labels such as **To Receive and Bill**, **To Bill**, **Completed**, **Stopped** and **Closed** describe business progress. A submitted document need not be operationally completed. Creating a draft invoice does not mean the supplier has been paid.

Many submitted fields are locked. Do not work around this with database edits. Linked downstream records can prevent cancellation. For a genuine return or credit, use the relevant return/credit process rather than erasing the original history.

Submission is not automatically managerial approval. A formal approval chain exists only if permissions and a Workflow have been configured for it.

## 5. Purchase stock: Material Request through supplier payment

### 5.1 Worked scenario

Your stores team needs 10 network cables. The supplier charges ₹100 per cable. For this learning example only, assume no tax, freight, discount or currency conversion, and zero opening stock. Real transactions must use the applicable tax setup.

### 5.2 Create the Material Request

1. Search **Material Request**, then select **New/Add**.
2. Select the test company and **Purpose = Purchase**. The field may also be described as the material request type.
3. Enter the Required By date.
4. Add `DEMO-CABLE`, quantity **10**, correct UOM and destination warehouse.
5. Expand the item row and check any row-level required date and warehouse.
6. Save. Check that you requested the intended goods, not a stock transfer or manufacture operation.
7. Submit, or follow the configured approval actions until it is submitted.

Expected result: the demand is recorded. No stock has arrived and no supplier payable exists merely because you submitted the request.

### 5.3 Create the Purchase Order from the request

1. Reopen the submitted request.
2. Select **Create → Purchase Order**.
3. The current v15 source opens an optional **For Default Supplier** prompt. Selecting a supplier filters to items whose company-specific default supplier matches it. Leave the optional filter empty when you do not intend that restriction.
4. Review the resulting Purchase Order draft. Select/confirm the actual Supplier, company, currency, required dates and destination warehouse.
5. Check the item quantities and source Material Request references. Enter or confirm **₹100** per unit.
6. Review supplier/billing/shipping addresses, taxes, charges, payment terms and total.
7. Save, review with the buyer/approver, then Submit.
8. Use the approved print/email procedure to communicate it to the supplier. Submission alone should not be assumed to send an email.

Expected result: an order for 10 units, ₹1,000 in this simplified example, linked to the request. Stock is still zero; the order is a commitment, not a receipt or bill.

**Partial ordering:** If you order 6 units from this request, the remaining 4 can be ordered later, subject to current linked quantities and status. For multiple suppliers, create separate Purchase Orders and allocate each source line/quantity correctly. Do not create a second independent full order for the same requirement.

**Alternative:** A new Purchase Order can fetch Material Requests through available **Get Items From** actions. The special open-requests-by-supplier action depends on item default-supplier configuration. Starting from the individual Material Request is simpler for a first exercise.

### 5.4 Optional supplier comparison

If you need competing prices, use **Request for Quotation → Supplier Quotation → Purchase Order**. Record the supplier's actual quote, terms and validity. A quotation is not an order. The direct Material Request → Purchase Order route remains useful when the supplier and price are already agreed.

### 5.5 Receive the goods

1. Open the submitted Purchase Order and select **Create → Purchase Receipt**.
2. Count and inspect the physical goods before entering the accepted quantity.
3. Check accepted warehouse, posting date/time, quantities and any serial/batch details.
4. For a partial delivery, enter only what actually arrived. Record rejected quantities and their warehouse appropriately if used.
5. Save and Submit after the warehouse operator checks the document.
6. Open **Stock Ledger** and **Stock Balance**, filter by company, item, warehouse and date, and confirm the movement.

Expected result for a full receipt: 10 units in stock. Under perpetual inventory, receipt normally also affects inventory accounting and the interim receipt liability; it does not replace the supplier's invoice.

### 5.6 Record the supplier's invoice

1. Open the submitted Purchase Receipt and choose **Create → Purchase Invoice**.
2. Check Supplier Invoice No, supplier invoice date, posting date, due date and supplier.
3. Compare item quantities, rates, taxes, charges and grand total against the supplier's bill and the agreed order.
4. Keep the receipt/order references. Resolve differences rather than silently changing unrelated documents.
5. For this separate-receipt flow, do not receive the same goods again using **Update Stock** on the invoice.
6. Save and Submit after accounting review.

Expected result: a supplier payable of ₹1,000 in the simplified example. **Accounts Payable** should show it outstanding. Received stock remains 10 units, not 20.

A direct Purchase Invoice with Update Stock is a different flow for receiving and billing together. Whether it is allowed depends on configuration. Choose one stock-receipt method for a given quantity. Services usually do not require a physical goods receipt.

### 5.7 Record payment

1. When the supplier has actually been paid, open the invoice and choose **Create → Payment** where available.
2. Verify Payment Entry type **Pay**, supplier, company and bank/cash account.
3. Enter the paid amount, payment date and bank/reference details.
4. Check that the invoice reference is present and the correct amount is allocated to it.
5. Save and Submit. Recheck the invoice's outstanding amount and Accounts Payable.

A submitted Payment Entry records payment in the ERP; it does not by itself instruct your bank to transfer money. An advance can be recorded before invoicing and later reconciled; an unallocated payment may leave an invoice showing outstanding until allocation is completed.

### 5.8 Why the Purchase Order button might be missing

| Check | Resolution |
|---|---|
| Request is Draft | Save and submit through the appropriate approval process |
| Purpose is Material Transfer/Issue/Manufacture | Use the corresponding stock/manufacturing flow; create the correct Purchase request if needed |
| Request is Stopped | Review the reason and authorized reopening process |
| All quantity is ordered | Inspect linked orders; there may be no remaining quantity to map |
| User lacks purchasing access | Ask the administrator to review role and document permissions |
| Supplier filter produces no items | Check Item Defaults or leave the optional filter empty |
| New UI hides action | Inspect the form's Create menu; report document state, role and screenshot to support |

The repository's Material Request client code checks submitted/not-stopped status and ordered percentage; the server mapping validates submitted state and Purchase type and maps eligible remaining rows.

## 6. Inventory operations

### Stock visibility

**Stock Balance** answers how much stock and value you have within the report's date/warehouse filters. **Stock Ledger** explains the sequence of movements and vouchers. Check UOM and posting dates when comparing reports. Actual quantity, reserved/planned quantities and projected quantity serve different purposes; a planned purchase is not physically available stock.

### Warehouse transfer

Use **Stock Entry**, purpose **Material Transfer**, for actual movement between warehouses. Enter source and target warehouses, item and quantity; save and submit after the move is confirmed. For 3 cables moved from Main Stores to Dispatch, Main Stores decreases by 3 and Dispatch increases by 3, while company-wide quantity remains unchanged.

A Material Request with purpose Material Transfer requests the move; it does not itself move inventory. Use in-transit handling only if your warehouse procedure is configured for it.

### Consumption or write-off

Use an approved **Material Issue** stock entry for internal consumption/write-off with appropriate accounts and cost center. Record the reason. A sale to a customer should follow the sales flow, not be hidden as internal consumption.

### Physical count and reconciliation

Count stock at an agreed cutoff and review in-flight transactions. Use **Stock Reconciliation** to set verified quantity/valuation where appropriate, with authorization and explanation of differences. It can affect financial balances; it is not a routine fix for unexplained ledger problems. Serialized/batched items require their supported tracking process.

### Reordering

Configure item reorder levels and quantities by warehouse only after understanding demand and lead times. Automatic material requests depend on configuration and scheduled processing. Check generated requests before ordering and avoid parallel manual requests for the same demand. A stopped VM cannot run scheduled jobs during its downtime.

## 7. Sell stock and collect payment

### 7.1 Quote and order

1. Create a **Quotation** for the customer or lead, with items, quantities, selling prices, taxes and validity.
2. On acceptance, create a **Sales Order** from the eligible submitted quotation, or enter an order directly if your policy permits.
3. Confirm customer, delivery date, warehouse, quantities, rate, taxes, terms and address.
4. Save and Submit through any configured approval process.

An order does not mean goods have left the warehouse or that the customer has paid. Check stock availability and any configured reservation process before promising delivery.

### 7.2 Pick and deliver

Use a Pick List if your warehouse process requires one. Create a **Delivery Note** from the Sales Order for the actual dispatched quantity. Confirm warehouse, serial/batch information, delivery address and posting date. Submit when dispatch is confirmed.

Example: deliver 4 of the 10 cables. Stock becomes 6. With perpetual inventory and the simplified cost of ₹100, the inventory cost of the 4 dispatched units is ₹400. Real valuation can differ due to costing method, charges, prior stock and later adjustments.

### 7.3 Invoice

Create a **Sales Invoice** from the Delivery Note. Check selling rate, tax, customer details, due date and source links. At ₹150 per cable, 4 cables total ₹600 before any tax or charges. Submit after review.

Do not also use Update Stock to dispatch the same four units again when the Delivery Note already posted the stock movement. A direct stock-updating sales invoice is an alternative flow, subject to settings.

### 7.4 Collect and allocate

After receiving customer money, create a **Payment Entry**, type **Receive**, linked to the invoice. Verify bank/cash account, date, paid/received amount and allocation. Submit, then inspect invoice outstanding and **Accounts Receivable**. A payment receipt records the event; it does not automatically collect funds from a customer's bank.

### 7.5 Partial fulfillment

Create separate deliveries for separate physical dispatches and bill the correct quantities. Review ordered, delivered and billed progress on the Sales Order. A partially paid invoice should retain only its unpaid balance. Close short-fulfilled orders only after a business decision, not simply to hide an overdue line.

## 8. Returns, corrections and exceptional cases

| Situation | Process to review |
|---|---|
| Supplier goods returned | Return against the original receipt and any necessary supplier debit-note/accounting adjustment |
| Customer goods returned | Sales return against original delivery/invoice and any necessary credit note/refund |
| Wrong draft | Correct before submission |
| Wrong submitted transaction | Check dependencies, then authorized cancellation/amendment or adjustment |
| Goods arrive before invoice | Receipt first; review received-not-billed position |
| Invoice arrives before goods | Accounting review of order-linked billing and receipt requirements |
| Advance to supplier/from customer | Payment Entry with correct party/references; later allocate/reconcile |
| Damaged inventory | Quarantine/inspection and approved return or write-off |
| Extra delivery or billing | Investigate tolerance/configuration and business approval rather than bypassing validation |

Physical returns, credit/debit documents and refunds are separate business events. A credit note without a stock movement does not necessarily return inventory; a stock return alone does not settle a financial refund. Review both stock and accounting ledgers after the complete correction.

Backdated and cancelled stock documents can trigger valuation/reposting implications. Coordinate with accounting for closed periods and do not assume deleting a visible record removes its history.

## 9. Accounting and management reports

| Report | Use | Key checks |
|---|---|---|
| Stock Balance | Quantity/value by item and warehouse | Company, cutoff date, warehouse, UOM |
| Stock Ledger | Investigate each stock movement | Item, warehouse, voucher, posting sequence |
| Accounts Payable | Supplier amounts due | Supplier, aging date, credits, allocated advances |
| Accounts Receivable | Customer amounts due | Customer, due dates, credits, payment allocation |
| General Ledger | Explain account postings | Company, period, account, party and voucher |
| Trial Balance | Review account balances | Period, opening balances and closing entries |
| Profit and Loss Statement | Income and expenses | Company, period, cost-center filters |
| Balance Sheet | Assets, liabilities and equity | As-of date and opening setup |

For pending purchases, inspect Purchase Order list filters and ordered/received/billed progress. For open sales, inspect Sales Order fulfillment. Report names and visibility can vary with version and permissions; search the exact report name.

**Illustration:** buying 10 units at ₹100 and selling 4 at ₹150 gives ₹600 sales and ₹400 cost of goods sold, hence ₹200 gross margin under the workbook's simplified assumptions. Supplier/customer cash timing does not by itself determine profit. Taxes, overhead, freight, discounts and valuation adjustments change real results.

## 10. Roles, approvals and customer access

Assign named users rather than sharing Administrator. Typical responsibility groups are Buying, Stock, Selling and Accounts; actual role permissions must be reviewed on your site.

| Responsibility | Expected tasks |
|---|---|
| Requester | Raise a Material Request and track it |
| Buyer | Compare suppliers and prepare orders |
| Warehouse operator | Receive, transfer, pick and dispatch actual goods |
| Accounts user/manager | Verify bills, payments, tax/account coding and reconciliation |
| Sales user/manager | Quote, order and coordinate fulfillment |
| System manager | Configure access and application settings |

Use Workflow configuration for approval thresholds such as high-value Purchase Orders. This is configuration work, not something this guide has activated. Test with ordinary role accounts; Administrator can conceal missing or excessive permissions.

A Customer/Supplier portal user has a different access model from an internal Desk user. Establish linked-party access and verify it before inviting external users. A second Company inside the same site should not be assumed to be a separate secure SaaS tenant; see the technical guide for deployment boundaries.

## 11. Daily operating routine

**Start of day:** check overdue orders, pending Material Requests, expected receipts/dispatches, low stock, overdue receivables and supplier payments due.

**During the day:** create linked documents at the actual event, verify quantities and references, attach supporting records and submit only after review. Keep physical movement and system posting aligned.

**End of day:** check drafts awaiting action, unmatched receipts/invoices, unallocated payments, negative/unexpected stock and failed communications. Review bank activity and scheduled downtime.

**Month end:** accounting reconciles bank, customer/supplier balances, inventory-to-ledger values, taxes, open receipt liabilities and period cutoffs before closing. Archive required reports under your company policy.

## 12. Troubleshooting and glossary

| Problem | First checks |
|---|---|
| Cannot see a document/module | Role, user permission, company restriction and search result |
| Cannot submit | Read validation message; required fields, date/period, accounts, workflow and permissions |
| Item not selectable | Disabled item, item type, company/defaults and search filters |
| Stock unchanged | Was a stock-moving document submitted? Correct warehouse/date? Maintain Stock enabled? |
| Invoice still outstanding | Payment submitted and allocated to this invoice? Credits/advances reconciled? |
| Price absent or wrong | Price list, currency, UOM, valid dates and item price |
| Totals do not match | Taxes, inclusive/exclusive rates, discount, rounding, exchange rate and charges |
| No email arrived | Email configuration/queue and recipient; submission may not send mail automatically |
| Website unavailable | VM running hours, administrator health check, connection/URL |

When reporting a problem include the document type and ID, company, your role, exact action, full error, time and a redacted screenshot. Do not send passwords or API keys.

**Master:** reusable record such as Item, Supplier or Warehouse. **Transaction:** an event such as a receipt or invoice. **DocType:** a document type/form definition. **UOM:** unit of measure. **Ledger:** chronological/accounting record of posted effects. **Outstanding:** unpaid/unallocated invoice balance. **Valuation:** inventory cost basis, not selling price. **Reconciliation:** matching records and resolving differences. **UAT:** a test environment for business acceptance.

## 13. Sources and scope

The detailed Material Request mapping was checked directly in the repository's `erpnext/stock/doctype/material_request/material_request.js` and `.py`. Other transaction instructions follow standard ERPNext v15 concepts and should be tested against your configured site. Official documentation can describe newer behavior, so source/version evidence takes precedence when it differs.

- [Material Request](https://docs.frappe.io/erpnext/material-request)
- [Purchase Order](https://docs.frappe.io/erpnext/purchase-order)
- [Purchase Receipt](https://docs.frappe.io/erpnext/purchase-receipt)
- [Purchase Invoice](https://docs.frappe.io/erpnext/purchase-invoice)
- [Buying Settings](https://docs.frappe.io/erpnext/buying-settings)
- [Payment Entry](https://docs.frappe.io/erpnext/payment-entry)

These references are technical provenance for maintainers and trainers. Publishing branded help inside Pridict is a separate task. Manufacturing, HR/payroll, advanced projects and statutory implementation require additional guides and configuration; they are outside this trading/distribution operating guide.
