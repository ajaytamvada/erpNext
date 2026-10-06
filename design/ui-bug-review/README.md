# Shared UI bug-fix checkpoint

The saved UI bug-fix changes were resumed and checked on the isolated local Process Intelligence
demo site. No UAT deployment or workflow redesign was performed.

## Verified fixes

- Workspace route normalization and Website/Administration ownership.
- Correct active rail section for native lists, forms and reports.
- Native workspace sidebar removal without removing contextual list/form sidebars.
- Compact quick-filter rows instead of duplicate list introduction cards.
- Preset application and All/reset on the current Sales Invoice and Purchase Order route.
- Notification styling on the dropdown panel rather than the navigation trigger.
- Notification panel containment at mobile widths.
- Suppression of duplicate page-context labels next to the shared breadcrumbs.
- Removal of negative top-level layout gutters that clipped mobile analysis content.

## Evidence

`documentation/process-intelligence/evidence/browser/ui-verification.json` contains 66 passing
assertions and names 14 screenshots from the successful run. It covers Website, Workflow State,
Sales Invoice, Purchase Order, Stock Entry and General Ledger at 1440px/light and 390px/dark,
plus notification panels. No uncaught JavaScript runtime exceptions were observed.

`documentation/process-intelligence/evidence/browser/verification.json` separately covers the
purchasing page in both themes at desktop and mobile widths, including the corrected gutters.
Run `node deployment/test-pridict-ui-routing.cjs` for eight focused route-classification cases.
See `documentation/process-intelligence/UI-IMPLEMENTATION.md` for local browser reproduction.

These are automated DOM, geometry and interaction checks with genuine captured screenshots.
Human visual sign-off remains pending. Existing PNGs and audit JSON in this directory are the
earlier saved review artifacts, not newly claimed visual acceptance of every product surface.
