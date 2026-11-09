"""Read-only SSH disk monitoring dashboard (reconstructed, sanitized)."""
import argparse
import json
import logging
import os
from pathlib import Path

import paramiko
from rich.console import Console
from rich.table import Table

LOG = logging.getLogger('ssh_storage_monitor')
CONSOLE = Console()


def load_servers(path):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    servers = data.get('servers')
    if not isinstance(servers, list) or not servers:
        raise ValueError('config must contain a nonempty servers list')
    names = set()
    for s in servers:
        if not isinstance(s, dict) or not all(s.get(k) for k in ('name', 'host', 'username')):
            raise ValueError('each server requires name, host and username')
        if s['name'] in names:
            raise ValueError('duplicate server name: ' + s['name'])
        names.add(s['name'])
    return servers


def select_servers(servers, names):
    if not names:
        return servers
    selected = [s for s in servers if s['name'] in names]
    missing = sorted(set(names) - {s['name'] for s in selected})
    if missing:
        raise ValueError('Unknown server(s): ' + ', '.join(missing))
    return selected


def disk_command(root_only):
    return "df -hP /" if root_only else "df -hP"


def monitor(server, root_only=False, timeout=10, insecure_host_keys=False):
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    if insecure_host_keys:
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    else:
        client.set_missing_host_key_policy(paramiko.RejectPolicy())
    kwargs = {
        'hostname': server['host'], 'port': int(server.get('port', 22)),
        'username': server['username'], 'timeout': timeout,
        'auth_timeout': timeout, 'banner_timeout': timeout,
        'look_for_keys': True, 'allow_agent': True,
    }
    if server.get('key_filename'):
        kwargs['key_filename'] = os.path.expanduser(server['key_filename'])
    if server.get('password_env'):
        password = os.environ.get(server['password_env'])
        if not password:
            raise ValueError('Missing password environment variable for ' + server['name'])
        kwargs['password'] = password
    try:
        client.connect(**kwargs)
        _, stdout, stderr = client.exec_command(disk_command(root_only), timeout=timeout)
        output = stdout.read().decode('utf-8', errors='replace').strip()
        error = stderr.read().decode('utf-8', errors='replace').strip()
        code = stdout.channel.recv_exit_status()
        if code != 0:
            raise RuntimeError('remote df failed: ' + (error or f'exit {code}'))
        return output
    finally:
        client.close()


def render(results):
    table = Table(title='SSH Storage Monitoring Dashboard')
    table.add_column('Server')
    table.add_column('Status')
    table.add_column('Disk usage / Error', overflow='fold')
    for name, status, detail in results:
        table.add_row(name, status, detail)
    CONSOLE.print(table)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Read-only SSH disk monitoring')
    parser.add_argument('--config', default='config.json')
    parser.add_argument('--servers', nargs='+', help='server names; omit for all')
    parser.add_argument('--root-only', action='store_true', help='show only filesystem containing /')
    parser.add_argument('--timeout', type=int, default=10)
    parser.add_argument('--insecure-auto-add-host-keys', action='store_true', help='LAB ONLY: trust unknown SSH keys')
    args = parser.parse_args(argv)
    logging.basicConfig(filename='connection_logs.log', level=logging.INFO,
                        format='%(asctime)s %(levelname)s %(message)s')
    try:
        servers = select_servers(load_servers(args.config), args.servers)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        CONSOLE.print(f'[red]Configuration error:[/red] {exc}')
        return 2
    results = []
    for server in servers:
        name = server['name']
        try:
            output = monitor(server, args.root_only, args.timeout, args.insecure_auto_add_host_keys)
            results.append((name, 'SUCCESS', output))
            LOG.info('Connection and disk check successful: %s', name)
        except (paramiko.SSHException, OSError, ValueError, RuntimeError) as exc:
            results.append((name, 'ERROR', type(exc).__name__ + ': ' + str(exc)))
            LOG.warning('Disk check failed for %s: %s', name, type(exc).__name__)
    render(results)
    return 1 if any(r[1] == 'ERROR' for r in results) else 0


if __name__ == '__main__':
    raise SystemExit(main())
