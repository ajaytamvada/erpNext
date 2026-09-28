# Pridict Redesign Milestone 11: Cross-Product Surfaces Source Handoff

Date: September 28, 2026

Status: Implemented in source only. Not visually reviewed, functionally verified, built, migrated, deployed, or accepted.

## Source scope

- Added one shared Desk classifier for native dialogs and transient interface surfaces.
- Added semantic treatments for assignment, sharing, email, print/PDF, workflow, import, export, filter, upload, confirmation, and generic dialogs.
- Added a compact Pridict eyebrow inside recognized native dialog titles without replacing modal headers, buttons, fields, or event handlers.
- Added shared treatment for notification panels, search results, autocomplete menus, uploads, messages, empty states, loading states, print output, keyboard focus, and narrow-screen dialogs.
- Reused the existing Pridict design tokens and CSS bundle instead of introducing a second theme system.

## Functional boundary

- Native dialog construction, validation, submission, cancellation, minimization, keyboard behavior, and callbacks remain unchanged.
- Assignment, sharing, workflow transitions, email sending, printing, PDF generation, import/export processing, file upload, and notification behavior remain owned by Frappe and ERPNext.
- The classifier reads visible dialog titles only to select presentation classes. It does not inspect field values, document content, recipients, attachments, permissions, or secrets.
- Existing print-format output remains white and document-controlled; the surrounding preview and toolbar receive the Pridict application treatment.
- Focus styling is additive and does not remove browser or framework keyboard semantics.

## Visible result

- Common dialogs use consistent depth, spacing, borders, controls, and responsive widths.
- Assignment, sharing, approval, data-operation, file, and confirmation dialogs receive concise contextual labels.
- Search and notification surfaces appear as structured Pridict panels rather than unrelated framework dropdowns.
- Upload, empty, loading, alert, toast, and print-preview states use consistent visual language across modules.
- Mobile dialogs use the available viewport while retaining native footer actions.

## Named exceptions

- Print Format Builder and other visual builders still require dedicated interaction review.
- Backup restore, system recovery, migration, console, and destructive administration tools require separate safety-focused review.
- Secret-bearing integration forms retain native protected controls and must not expose values through summary components.
- Browser-native dialogs, operating-system file pickers, generated PDFs, letterheads, and customer-authored print/email content are outside this presentation adapter.
- Unrecognized dialogs receive the shared base treatment but no potentially misleading contextual label.

## Validation

- JavaScript syntax validation passed for the cross-product classifier.
- A focused simulated-DOM check verified assignment-dialog classification and idempotent eyebrow insertion.
- SCSS brace validation, hook registration checks, bundle import checks, and `git diff --check` passed.
- No Frappe browser runtime was available, so native modal event behavior, focus trapping, editor layout, dropdown positioning, print preview, and mobile interaction remain unverified.
- No asset build, browser screenshots, email sending, file upload, import/export execution, workflow action, broad test suite, image build, migration, or deployment was run.

## Next target

Perform a source completeness audit against the execution plan and enumerated enabled surfaces. Close remaining genuine exceptions with focused adapters where justified, then prepare a consolidated implementation handoff and an explicit runtime test matrix for the user-led verification pass.

Do not treat this handoff as runtime acceptance or deployment readiness.
