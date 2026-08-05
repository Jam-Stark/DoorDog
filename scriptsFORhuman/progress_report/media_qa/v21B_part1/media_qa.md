# v21B Part 1 Media QA

Full CPU/OpenCV decode: PASS for every finalized MP4.

Matrix SHA-256: `eff869d458caf06e9bb40419506e261f03d327479e093bf59d879d53c5382ce3`

## v21B_B1_step0500

- Counts: primary 48, auxiliary 12, finalized 60, writing 0.
- Selected canonical set: env0002 / episode0000 / main, handle_top, handle_side.
- Contact sheet: `v21B_B1_step0500_env0002_episode0000_contact.png`.
- Non-varying five-position sampled hashes: 12.

## v21B_B3_step1250

- Counts: primary 48, auxiliary 6, finalized 54, writing 0.
- Selected canonical set: env0002 / episode0000 / main, handle_top, handle_side.
- Contact sheet: `v21B_B3_step1250_env0002_episode0000_contact.png`.
- Non-varying five-position sampled hashes: 6.

## v21B_B4_step1250

- Counts: primary 48, auxiliary 9, finalized 57, writing 0.
- Selected canonical set: env0002 / episode0000 / main, handle_top, handle_side.
- Contact sheet: `v21B_B4_step1250_env0002_episode0000_contact.png`.
- Non-varying five-position sampled hashes: 9.

## Limits and findings

- Exact primary identity/cardinality gate: PASS (48 each; total 144).
- All  finalized media decoded fully with reported-frame-count equality and stable frame shape.
- Sample-hash variation across every finalized media: FAIL; 27 auxiliary clip(s) are static at the five sampled positions. This is recorded, not substituted for primary evidence.
- Qualitative only: no policy-success, release, true applied torque, or hardware claim. v21B remains `COMPLETED_SCIENTIFIC_NO_RELEASE`; torque remains `ESTIMATE_ONLY`.
