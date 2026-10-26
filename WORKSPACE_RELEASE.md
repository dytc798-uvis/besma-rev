# BESMA HQ workspace release · 2026-10-26

Scoped additive release from production source 3100a2c. The existing Vue bundle is retained; authenticated HQ roles receive eight menus. Current API authorization, document workflows, evaluations and signatures are preserved.

- New module: backend/app/modules/workspace.py; main.py adds its router only.
- New authenticated dataset: /srv/besma/storage/headquarters-workspace (not tracked in Git).
- New table: workspace_site_preferences. All existing tables must be unchanged during migration.
- Functional evaluation criteria and June deadline remain unchanged. This release opens navigation, not a new assessment period.
- Accounting tasks use the HRD capture; safety and emergency reference duties are marked temporary. Budget/estimate tasks await real assignments.
- Latest NAVERWORKS Drive comparison remains unverified; forms show registered BESMA materials without claiming latest Drive synchronization.
- Background photos are existing public company assets. Internal contact/case/policy data are served only after HQ authentication.

Build with Node and the locked esbuild dependency:

    npm ci
    npm run build -- <task-root> <verified-prior-static-directory>

The task root contains the verified previous prebuilt artifact, its SHA-256 manifest and the private dataset. The build verifies preservation of all 114 pre-existing non-index assets. CSS/JS filenames are content hashed.

Validation: isolated server Python/API checks; 8-menu desktop and 390/320px mobile UI; original Vue login and shell DOM retention. Manual examples use synthetic names/phones.

Roll back the frontend to the previous verified Vercel deployment. Restore backend main.py from the timestamped NCP backup and restart the service. Retain the additive preferences table and private source copies for inspection; do not restore a database over later live records.
