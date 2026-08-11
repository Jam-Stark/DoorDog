# Pull v1–v4 Evidence ZIP Handoff

Canonical detailed manifest: [MANIFEST.md](MANIFEST.md)
Build receipt: [P0_C_EVIDENCE_ZIP_RECEIPT.md](../pull_v5/evidence_zip_work/P0_C_EVIDENCE_ZIP_RECEIPT.md)

- Root archive: `a2_piper_pull_v1_to_v4_evidence_20260811.zip`
- Final size: `302,913,787` bytes (`≤500,000,000` decimal cap)
- Archive layout: `195` unique entries
- Tier1: `97`; Tier2: `22`; omitted Tier2 MP4 logical entries: `6`
- Tier3: `75` all-row field-projected step traces, one-to-one with the 75 formal metric cells
- Tier3 original source bytes: `22,665,835,160`
- Tier3 projected source bytes: `1,250,007,189`
- Tier3 compressed ZIP payload bytes: `194,484,166`

Tier3 projections preserve every source trace row in original order/count and retain the analyzer-required fields for episode identity, stage/event timing, reward activation, and inherited invariants. Original evidence units remain untouched. No hashes or content-digest fields are used.
