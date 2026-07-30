# R1 BLOCKED — DO NOT EXECUTE

The historical base_v20_R1 execution chain is closed as an admission blocker.
Its scientific claim and immutable B0 inputs remain read-only evidence; they are
not runtime authorization. Every executable CLI in this directory exits with
code `2` unless the caller explicitly sets
`BASE_V20_ALLOW_BLOCKED_R1_EXECUTION` in its own environment.

The R2 tools never set that opt-in variable and must not import R1 producers or
consumers. This marker does not alter safe module imports or immutable B0 files.
