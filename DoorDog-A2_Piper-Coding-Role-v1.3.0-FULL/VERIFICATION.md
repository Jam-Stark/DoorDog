# DoorDog A2_Piper Jam Coding Role v1.3.0 — Verification

## Completed checks

```text
Python syntax compilation                              PASS
JSON parse: opencode / Claude / Codex hooks / OMO      PASS
TOML parse: team state / artifact targets / sync       PASS
Unit tests                                             8 / 8 PASS
Inactive team-state status has no filesystem side effect PASS
Adaptive unregistered spawn remains allowed           PASS
Strict controlled writer requires valid contract      PASS
Exclusive lease conflict detection                    PASS
Formal freeze + verdict invalidation                   PASS
Artifact pack without explicit handoff confirmation   BLOCKED AS DESIGNED
Dirty migration without Git choice                    BLOCKED AS DESIGNED
Explicit authorized checkpoint + migration commits    PASS
v1.2.0 -> v1.3.0 synthetic upgrade                    PASS
Protected .codex/config.toml                           BYTE-IDENTICAL
Protected .codex/agents/                               BYTE-IDENTICAL
Migration leaves team state inactive                   PASS
Managed v1.2 .gitignore block upgraded to v1.3         PASS
No __pycache__ / .pyc included or committed            PASS
ZIP CRC / unzip -t                                     PASS
```

## Evidence boundary

These checks validate the package, configuration, scripts and a synthetic Git migration. They do not establish:

```text
production DoorDog worktree migration                  NOT RUN HERE
real Codex MultiAgentV2 session                        NOT RUN
real OMO Team Mode session                             NOT RUN
IsaacLab simulation                                    NOT RUN
training or formal evaluation                          NOT RUN
Google Drive upload                                    NOT RUN
A2 / PiPER hardware action                             NOT RUN
```

The local deployment AI must report the actual two commit SHAs and protected-path verification from the target worktree.
