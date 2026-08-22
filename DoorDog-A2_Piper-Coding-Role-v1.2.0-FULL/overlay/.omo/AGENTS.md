# DoorDog OpenCode / OMO adapter

Root `AGENTS.md` and `.ai/*` are canonical. This file only maps OMO capabilities.

- Use ordinary delegation for simple/normal work.
- Use `task(category=...)` and `task(subagent_type=...)` according to current OMO semantics; do not mix them in one call.
- Enable Team Mode only when shared tasks、member mailbox or multiple independent writers provide real value.
- Team Mode retains official lifecycle: create -> task claim/update/message -> shutdown request/ack -> delete.
- Ineligible specialists remain ordinary delegated agents rather than direct team members.
- Lead owns scope、lease、review arbitration、memory promotion、Git and external writes.
- Team members may exchange bounded findings and requests, but cannot expand authority.
- Standalone Claude Code remains single-agent even when OMO uses a Claude-family provider.
