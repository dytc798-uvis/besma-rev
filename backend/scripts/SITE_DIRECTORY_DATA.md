# Private site directory preparation

`prepare_site_directory_safety.py` reconciles the private baseline with the latest
employee and daily employee registrations and NAS 105 current safety assignments.
Use its matching requirements file. Only names, phones, ranks, roles, site codes
and employment status are projected; raw employee exports stay at their source.
User confirmed assignments and Workbench overrides remain separate private inputs.

`prepare_site_directory_contracts.py` accepts a reviewed private site-to-folder map
under the approved NAS cost root. Use its matching requirements file. It selects
the latest amendment of each contract, separates work contracts, and totals only
verified VAT exclusive amounts. Scanned or conflicting amounts remain unknown.
Any visually verified supplement must include the exact source SHA-256.

Keep all input snapshots, maps, outputs, source manifests and reconciliation
reports private. Do not commit or publish them as static assets. The authenticated
directory API reads the production snapshot from storage/site-directory/directory.json.

Contact ranks are stored in `site_directory_contact_ranks` by stable person ID.
Rank edits are shared across authorized HQ_SAFE users and use revision checks;
all changes in a save are committed atomically. Source refresh does not overwrite
these database edits. Favorites remain private to the authenticated user.
