# Ops Runbook

Populated during M7. Required sections, each with real commands and real
timestamps from actually performing the procedure once:

1. Backup and restore drill (procedure + last drill date + measured RTO)
2. Attempts partition management (monthly create; draining attempts_default)
3. Pulling a disputed exercise (status flip + cache key delete)
4. Rotating JWT_SECRET and TOKEN_ENC_KEY
5. LLM provider degradation playbook (thresholds, what degrades, what to watch)
6. Alert catalog (what fires, where it pages, first response per alert)
