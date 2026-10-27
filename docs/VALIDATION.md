# Validation evidence

- 14 backend tests passed: exact linguistic feature values, abbreviation/decimal segmentation, six prose scenarios with abstention, detector protocol, failed jobs/unsupported language, actual PDF and DOCX extraction including table order, invalid/oversized/image-only uploads, persistence, consent, profiles, comparison deltas, PDF/JSON/TXT exports, report-guide context, deletion, origin checks, retention and ephemeral deletion. Two evaluation tests cover known metrics and cross-split leakage. These are software tests, not scientific detector validation.
- Production TypeScript/Vite build passed. Vite reports a bundle-size advisory; chart code splitting is an optimization opportunity.
- Two Chromium end-to-end tests passed: analysis, save, real PDF download, opt-in profile, persistence after reload, navigation, theme toggle, and mobile editor/navigation without horizontal overflow. An initial navigation accessible-name failure was fixed and both tests rerun successfully.
- Production JavaScript dependency audit reported zero known vulnerabilities at validation time. This is not a full security audit.
- Reusable install script completed successfully. Startup script verified health, frontend delivery, a real nine-word analysis with null authorship probability and result deletion.
- Docker deployment, fresh cloud snapshot restoration, public multi-user operation and ML model accuracy were not tested. No validated detector, external search, OCR or conversational provider is installed.
- Screenshots in this directory show actual browser-test state, not seeded user data. Test data used isolated storage under /tmp; the normal workspace starts empty.

The sandboxed FastAPI TestClient hung because of restricted execution capabilities; the same tests passed using the approved execution path. Browser CDN access was denied by policy; installed system Chromium was used without changing network policy or TLS settings.
