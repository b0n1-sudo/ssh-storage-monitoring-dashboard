# SSH Storage Monitoring Dashboard

A **sanitized reconstruction** of a Python SSH disk-monitoring utility developed during SOC operations work (2024–2025). This is **not a verified copy of the original source**.

## Features
- Checks disk usage across multiple configured Linux servers over SSH (`df -hP`).
- Supports all-server or selected-server monitoring.
- Optional `--root-only` mode checks the filesystem containing `/` (`df -hP /`).
- Displays per-server results and errors in a Rich terminal table.
- Logs successful and failed checks without storing passwords.
- Supports SSH keys, SSH agent, and password values supplied through environment variables.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate  # Windows PowerShell: .venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
cp config.example.json config.json  # Windows: copy config.example.json config.json
# Edit config.json to include only systems you are authorized to access.
python main.py --config config.json
python main.py --config config.json --root-only
python main.py --config config.json --servers server-a
```

Use SSH host keys already present in your system's `known_hosts` file (for example, after verifying the host fingerprint through an authorized channel). The optional `--insecure-auto-add-host-keys` flag disables that protection and should be used only in isolated labs.

## Security and scope
- Do not commit `config.json`, private keys, credentials, customer information or log files.
- The sample hostnames are placeholders, not real endpoints.
- This program runs read-only disk usage commands on explicitly configured hosts; it does not discover or scan networks.
- The original project's interactive yes/no/exit selection, pending-state UI, jump-host support and exact original logging format are **not reproduced** in this reconstruction.
- No production deployment or performance metrics are claimed.

## Background
Based on remembered features of the original Python/Paramiko/Rich dashboard: SSH checks, `df -h`, server selection, root-only filtering, error handling, JSON configuration, and connection logs. The code here is newly authored for portfolio publication.
