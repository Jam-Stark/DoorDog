# P0-c Evidence ZIP Receipt

- TASK_ID: `A2_PULL_V5_20260812_ZIP`
- Revision: `r1`
- Status: `PASS`
- Builder: `scriptsFORhuman/pull_v4/build_pull_v1_v4_evidence.py`
- Manifest: `scriptsFORhuman/pull_v4/MANIFEST.md`
- Root archive: `a2_piper_pull_v1_to_v4_evidence_20260811.zip`

## Inventory

- Tier1: 97 entries (10 configs/runtime configs, 75 formal metrics, 12 full training logs).
- Tier2: 22 entries (four render receipts/failure receipt plus 18 MP4s); six logical R1 omissions remain explicit.
- Tier3: 75 entries, one-to-one with the 75 formal metric cells. Each projected JSON retains every original stage2-5 row in original order and count, with only analyzer-required fields. The original trace source path, original byte count, projected byte count, row count, and dotted projected-field list are recorded per cell in the manifest's `Tier-3 projected trace inventory`.
- Tier3 original source bytes: `22,665,835,160`.
- Tier3 projected source bytes: `1,250,007,189`.
- Tier3 compressed ZIP payload bytes: `194,484,166`.

## Archive checks

- Final ZIP size: `302,913,787` bytes, below the decimal `500,000,000`-byte cap.
- Entries: `195` total (`97 + 75 + 22 + MANIFEST.md`), all names unique.
- All 75 `step_traces/*__stage2_5_step_trace.json` entries are present and non-empty.
- Embedded `MANIFEST.md` matches the regenerated manifest file.
- No ZIP temporary/reserve entries; no root temporary rebuild files remain.
- Rebuild projections and temporary files are confined to `scriptsFORhuman/pull_v5/evidence_zip_work/`.
- Source evaluation units were not modified. No content-digest fields or hash calculations were added.

## Commands

- `python3 scriptsFORhuman/pull_v4/build_pull_v1_v4_evidence.py plan --renders` — PASS.
- `python3 -m py_compile scriptsFORhuman/pull_v4/build_pull_v1_v4_evidence.py` — PASS.
- `python3 scriptsFORhuman/pull_v4/build_pull_v1_v4_evidence.py build` — PASS; final size and Tier counts printed above.
- Final archive/layout inspection (ZIP names, counts, sizes, embedded manifest, cap, temporary-path audit) — PASS.
