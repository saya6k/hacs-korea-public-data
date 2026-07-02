---
name: publishing-conventions
description: How saya6k/ha-* HACS repos publish docs and what must be enabled when creating a new one
metadata: 
  node_type: memory
  type: project
  originSessionId: afcab7c3-0676-4a97-987c-d8a9a6c1806c
---

Across the `saya6k/ha-*` HACS integration repos (all except `ha-apps`), each repo publishes its own bilingual Zensical docs to GitHub Pages via a `docs.yml` workflow that runs only on release (release-please). The manifest `documentation` field should point at the **published docs site** `https://saya6k.github.io/<repo>/` (root redirects to `/en/`), NOT at the GitHub repo URL. `issue_tracker` stays as `https://github.com/saya6k/<repo>/issues`.

**Why:** the "Documentation" link in HACS/HA should open the actual docs, not the source repo.

**How to apply (for a brand-new repo):** two repo settings are OFF by default and break the release/docs pipeline until fixed:
1. `gh api --method PUT repos/saya6k/<repo>/actions/permissions/workflow -f default_workflow_permissions=write -F can_approve_pull_request_reviews=true` — otherwise release-please fails with "GitHub Actions is not permitted to create or approve pull requests".
2. `gh api --method POST repos/saya6k/<repo>/pages -f build_type=workflow` — otherwise `actions/deploy-pages` fails with 404 "Ensure GitHub Pages has been enabled".

Established repos already have both enabled. `docs.yml` here was given a `workflow_dispatch` trigger so docs can be redeployed on demand (re-running a failed docs job in the same run accumulates duplicate `github-pages` artifacts and fails — dispatch a fresh run instead). See [[release-flow]].
