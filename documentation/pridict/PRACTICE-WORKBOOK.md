# Pridict practice workbook

Trading/distribution exercise — 17 September 2026.

Use a designated test company/site with authorization to create test transactions. Do not enter fictitious transactions in real company books. These steps have not been executed by this documentation task.

## 1. Prepare

Ask your administrator/accountant to confirm:

- Company and company-specific warehouse for this exercise.
- Stock item `DEMO-CABLE`, UOM `Nos`, no opening quantity, no serial/batch tracking for this introductory example.
- Supplier `Demo Supplier` and Customer `Demo Customer`.
- Correct company accounts, cost center and a test bank/cash account.
- Access for Buying, Stock, Selling and Accounts actions, or separate users who will perform their steps.
- An open posting period and appropriate dates.

The example deliberately excludes taxes, freight, discounts and foreign currency. This is a teaching assumption, not permission to omit applicable taxes from real transactions. Use a fresh item or reconcile its opening position so unrelated movements do not distort the expected results.

## 2. Purchase 10 units

| Step | Action | Expected result | Record evidence |
|---|---|---|---|
| 1 | Create Material Request, Purpose Purchase, 10 cables, required date and warehouse; submit | Demand for 10; actual stock 0 | Material Request ID |
| 2 | From request, Create → Purchase Order; supplier, 10 × ₹100; submit | Order value ₹1,000; stock 0 | PO ID; source request link |
| 3 | From PO, create Purchase Receipt for 10 accepted units; submit | Stock +10; balance 10 | Receipt ID; Stock Ledger voucher |
| 4 | From receipt, create Purchase Invoice ₹1,000; keep Update Stock off; submit | Supplier outstanding ₹1,000; stock remains 10 | Invoice ID; Accounts Payable row |
| 5 | Record actual simulated test payment ₹1,000 through Payment Entry, Pay; allocate invoice; submit | Invoice outstanding 0 | Payment ID; allocation and bank ledger |

Before moving to the next step, check the linked source document. If an expected figure differs, investigate instead of creating compensating entries blindly.

## 3. Sell 4 units

| Step | Action | Expected result | Record evidence |
|---|---|---|---|
| 6 | Create Sales Order for customer, 4 × ₹150; submit | Sales commitment ₹600; stock still 10 | Sales Order ID |
| 7 | From order create Delivery Note for 4 from the receipt warehouse; submit | Stock -4; balance 6 | Delivery ID; Stock Ledger voucher |
| 8 | From delivery create Sales Invoice ₹600, without another stock update; submit | Customer outstanding ₹600; stock remains 6 | Sales Invoice ID; Accounts Receivable row |
| 9 | Payment Entry, Receive ₹600, allocate invoice; submit | Customer outstanding 0 | Payment ID and allocation |

## 4. Reconcile the whole exercise

With no other transactions or valuation differences:

| Measure | Expected |
|---|---:|
| Purchased quantity | 10 |
| Delivered quantity | 4 |
| Remaining quantity | 6 |
| Remaining inventory value | ₹600 |
| Sales revenue | ₹600 |
| Cost of goods sold under perpetual inventory | ₹400 |
| Gross margin before overhead and tax | ₹200 |
| Supplier invoice outstanding after full allocation | ₹0 |
| Customer invoice outstanding after full allocation | ₹0 |
| Net change in bank/cash from these two payments | -₹400 |

The bank balance need not be -₹400; that is the **change** caused by this exercise. A payment to a supplier and receipt from a customer affect cash timing, while inventory and margin follow the stock/accounting events. Use the same company, period, warehouse and item filters when comparing reports.

## 5. Additional practice cases

Use separate test records for each case. Record expected results before submission.

1. **Partial order:** request 10, order 6; verify only the remaining eligible quantity is offered for later ordering.
2. **Partial receipt:** order 10, receive 6, later receive 4; verify total received is 10, not 16 or 20.
3. **Partial customer payment:** invoice ₹600, allocate ₹200; verify ₹400 remains outstanding.
4. **Warehouse transfer:** move 2 of the remaining 6 from Main Stores to Dispatch; verify company total is 6 and warehouse balances are 4 and 2.
5. **Return:** with accounting supervision, return one delivered unit using linked return/credit documents; verify physical stock, customer credit and any refund separately.
6. **Permissions:** repeat access checks as a buyer, warehouse operator and accounts user. Confirm users cannot perform restricted actions or view restricted company data.
7. **UI coverage:** open the same documents in light/dark themes and on a narrow screen; check item-row editing, totals, validation, menus and linked-document navigation.

## 6. Acceptance record

Copy this block for each scenario:

```text
Date / tester:
Application release / image:
Company / user roles:
Scenario:
Document IDs:
Expected result:
Actual result:
Report filters and evidence:
Pass / fail / blocked:
Issue and owner:
```

A screenshot of an attractive dashboard is not sufficient workflow evidence. Keep the source links, stock ledger and outstanding balances with the acceptance record. Do not delete submitted exercise history casually; use an agreed disposable environment or an authorized cleanup/restore procedure.
