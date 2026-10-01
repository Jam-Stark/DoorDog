# Codex team v1.5.0

Root AGENTS.md and Owner authority remain controlling. Read .ai/MODEL_ROUTING.md before delegation. Main model and effort are App-owned. Default children use GPT-6 Sol/medium; retrieval and mechanical work use Luna; bounded implementation/review uses GPT-6 Sol. Only deep_researcher may use GPT-6 Astra, at medium, with one persistent child identity per team. No nested teams, spawn model/effort overrides, or whole-history forks. Current verified MultiAgentV2 uses explicit fork_turns="none".

FAST: do the work directly. STANDARD: delegate only where independent work, specialized context, or a concrete review concern provides real benefit. Usually 0–2 children; 5 is a ceiling, not a target. Give a focused brief with exact question, paths, facts, write set, acceptance and limits. A child does not own Git, external authority or broader scope.

Register the actual Main session and stable Owner task/team ID before spawning. Native PreToolUse reserves the quota; PostToolUse binds identity. Unknown tool shapes fail closed or retain a reservation. Verify actual hook interception/effective model/effort locally; static config is not billing enforcement. Do not route agent-control calls through an uncovered tool or Code Mode path.

Two independent Main teams use .ai/SESSION_PROTOCOL.md for direct plan/STOP/result exchange, with one in-flight notification and durable event IDs. Children communicate with their own Main. An addressed peer message is not a grant of Owner authority. Within the pre-authorized plan envelope, workers can continue after a planner decision without asking Owner to relay text. Any new high-risk side effect, scope expansion or Owner-only STOP still requires Owner action.

Persistent full coordination remains conditional: .ai/TEAM_STATE.md for genuine write/resource conflicts, formal reviews or DAG ownership. v1.5.0's small cost/outbox ledger does not turn every read-only task into a full approval workflow. Preserve legacy coordination validation; never infer acceptance from command success.

Long jobs keep their existing supervisor, ETA-based single logical wait and durable completion receipts. No agent hired to poll logs; no Stop hook loop. Tool/MCP ownership and cleanup: .ai/TOOL_LIFECYCLE.md. Never reap authorized training, shared services, the Codex App or the shared app-server as ephemeral tools.

Close only owned, activated children and ephemeral resources. On resume/compact retain the same team identity, Astra allocation and pending outbox. No mandatory memory/artifact phase and no automatic queue acknowledgement turns.
