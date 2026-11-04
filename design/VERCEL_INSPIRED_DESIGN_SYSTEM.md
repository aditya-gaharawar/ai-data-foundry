# AI Data Foundry — Vercel-inspired design system

Use **Vercel Geist as inspiration** for strong developer-tool UX, without copying trademark assets or passing the product off as affiliated. Visual tone: black/white, restrained grays, excellent typography, precise borders, powerful code experiences, polished interactions, functional status visualization. Consult https://vercel.com/geist/introduction and verify license terms for chosen font/icon dependencies.

## Design tokens
- Font: Geist Sans / Geist Mono if legitimately installed and licensed; fallback `Inter, ui-sans-serif, system-ui`, mono `ui-monospace`.
- Scale: 4px primitive, 8px spacing rhythm, 12-col main grid; common container max 1440px.
- Radius: 6px input, 8px card, 10px overlay; only meaningful elevation.
- Light: canvas `#FFF`, muted `#FAFAFA`, text `#171717`, subtle `#666`, hairline `#EAEAEA`.
- Dark: canvas `#0A0A0A`, muted `#111`, text `#EDEDED`, subtle `#A1A1A1`, hairline `#333`.
- Focus: visible blue focus; status uses semantic green/amber/red that meets WCAG contrast.
- Code surfaces: high-contrast syntax highlighted editor, copy affordance and line numbers.
- Motion: 120-180ms modest transitions, obey `prefers-reduced-motion`, no gratuitous animated effects.

## App shell
Desktop left sidebar (collapsible), project switcher, command menu Ctrl/Cmd+K, top breadcrumb/title, meaningful search, account/notifications, responsive 360px mobile drawer, live error and incident banners. Use server-rendered initial state where appropriate. Add a keyboard shortcut guide.

## Priority components and functional behavior
- **CreateDatasetDialog:** validates modality/name/schema -> real POST -> navigates to persisted resource.
- **RunButton:** validates recipe, checks auth/provider/compute/budget -> POST -> displays actual job state and trace.
- **SampleGallery:** real signed images/audio/video or formatted JSON/text; pagination and loading/errors.
- **ComputeSelector:** only eligible compatible pools, pricing estimate, honest unavailable state.
- **APIKeyManager:** create one-time view, copy, revoke; redacted GET and audit.
- **WebhookPanel:** registered endpoint, secret rotation, delivery attempts and verified replay.
- **PipelineCanvas:** structural nodes map 1-to-1 with validated recipe DSL; no ornamental nodes.
- **LogViewer:** chronological structured worker logs, filter/export, correlation IDs.
- **UsageView:** actual metered samples, tokens, storage, job time, budget; separate demo fixture.

## Screen verification matrix
Every page must specify API source, mutations, permission scopes, empty/loading/error/no-config states, mobile behavior, keyboard navigation, test ID and a passing Playwright journey. For new pages, add screenshots under `tests/e2e/screenshots/` and ensure they compare against reviewed baselines. Axe checks on primary paths; manual keyboard test before marking done.

## Layout quality checks
Test 360, 390, 768, 1024 and 1440 widths. Review large datasets (10k+ rows) for virtualized tables and paginated API queries; do not render a million rows in the browser. Ensure 200% zoom works. No forced horizontal scrolling for the main app shell; long tables may scroll within a labeled container.
