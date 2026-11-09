# SSH Storage Monitoring Dashboard

A sanitized **reconstruction** of a terminal-based monitoring project developed during SOC analyst work (2024–2025). This is not the original production source code.

## Features

- Interactive server selection (`all`, comma-separated names, `exit`), plus `yes/no/exit` confirmation
- Rich live table with **yellow PENDING**, **bright green SUCCESS**, **bright red ERROR**
- Remote read-only `df -hP` or `df -hP /` (`--root-only`)
- Optional single-hop SSH jump-host transport using Paramiko `direct-tcpip`
- Error handling and local connection logging (exact historical format not recovered)
- SSH host-key verification enabled by default
- Offline `--demo` mode showing **fictional** data, without making network connections

## Windows PowerShell setup

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item config.example.json config.json
python main.py --config config.json --demo
```

Use `python main.py --config config.json` for authorized real hosts, after configuring SSH keys and host-key trust. Use `--servers server-a server-b` to skip the interactive menu. Use `--root-only` to inspect the root filesystem. Use `--help` for more options.

## Security and scope

- **Never commit** `config.json`, credentials, SSH private keys, customer information, or log files.
- All example hosts are fictional placeholders, not actual endpoints.
- This script does not scan networks; it runs read-only disk commands only on configured, authorized servers.
- The jump-host implementation is a **new reconstruction**; its exact historical implementation and original working status are unverified.
- The original logging format is **not recovered**. The implementation logs generic configured server labels and error types.
- No claims of production deployment or measured performance are made.
- Do not enable `--insecure-auto-add-host-keys` outside a controlled test lab.

## Tests

```powershell
python -m unittest discover -s tests -v
```

## Portfolio note

This repository illustrates technical work in Python, Paramiko, SSH, Rich, Linux storage commands, and security operations. It contains no customer-specific infrastructure or operational credentials.
