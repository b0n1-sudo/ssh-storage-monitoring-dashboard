"""Sanitized reconstruction of an interactive, read-only SSH disk dashboard."""
import argparse
import json
import logging
import os
from pathlib import Path

import paramiko
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

CONSOLE = Console()
LOG = logging.getLogger('ssh_storage_monitor')


def load_servers(path):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    servers = data.get('servers')
    if not isinstance(servers, list) or not servers:
        raise ValueError('config must contain a nonempty servers list')
    names = set()
    for server in servers:
        if not isinstance(server, dict) or not all(server.get(k) for k in ('name', 'host', 'username')):
            raise ValueError('each server requires name, host and username')
        if server['name'] in names:
            raise ValueError('duplicate server name: ' + server['name'])
        names.add(server['name'])
        for key in ('port',):
            if key in server and not (1 <= int(server[key]) <= 65535):
                raise ValueError('invalid port for ' + server['name'])
        jump = server.get('jump_host')
        if jump is not None:
            if not isinstance(jump, dict) or not all(jump.get(k) for k in ('host', 'username')):
                raise ValueError('jump_host requires host and username')
    return servers


def select_servers(servers, names):
    if not names:
        return servers
    wanted = [n.strip() for n in names if n.strip()]
    by_name = {s['name']: s for s in servers}
    missing = [n for n in wanted if n not in by_name]
    if missing:
        raise ValueError('Unknown server(s): ' + ', '.join(missing))
    return [by_name[n] for n in dict.fromkeys(wanted)]


def disk_command(root_only):
    return 'df -hP /' if root_only else 'df -hP'


def connection_options(server, timeout):
    options = dict(hostname=server['host'], port=int(server.get('port', 22)),
                   username=server['username'], timeout=timeout, auth_timeout=timeout,
                   banner_timeout=timeout, look_for_keys=True, allow_agent=True)
    if server.get('key_filename'):
        options['key_filename'] = os.path.expanduser(server['key_filename'])
    if server.get('password_env'):
        password = os.environ.get(server['password_env'])
        if not password:
            raise ValueError('Missing password environment variable for configured server')
        options['password'] = password
    return options


def ssh_client(insecure=False):
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy() if insecure else paramiko.RejectPolicy())
    return client


def monitor(server, root_only=False, timeout=10, insecure_host_keys=False):
    """Connect directly or via a single optional SSH jump host; execute read-only df."""
    target = ssh_client(insecure_host_keys)
    jump = None
    channel = None
    try:
        opts = connection_options(server, timeout)
        if server.get('jump_host'):
            jump_config = server['jump_host']
            jump = ssh_client(insecure_host_keys)
            jump.connect(**connection_options(jump_config, timeout))
            transport = jump.get_transport()
            if transport is None or not transport.is_active():
                raise paramiko.SSHException('Jump host transport unavailable')
            channel = transport.open_channel('direct-tcpip',
                (server['host'], int(server.get('port', 22))), ('127.0.0.1', 0), timeout=timeout)
            opts['sock'] = channel
        target.connect(**opts)
        _, stdout, stderr = target.exec_command(disk_command(root_only), timeout=timeout)
        output = stdout.read().decode('utf-8', errors='replace').strip()
        error = stderr.read().decode('utf-8', errors='replace').strip()
        code = stdout.channel.recv_exit_status()
        if code != 0:
            raise RuntimeError('remote disk command failed: ' + (error or 'nonzero exit status'))
        return output
    finally:
        target.close()
        if channel is not None:
            channel.close()
        if jump is not None:
            jump.close()


def dashboard(rows, root_only=False):
    table = Table(title='[bold bright_cyan]SSH STORAGE MONITORING DASHBOARD[/bold bright_cyan]',
                  header_style='bold bright_cyan', expand=True, show_lines=True)
    table.add_column('SERVER NAME', style='bold white', no_wrap=True)
    table.add_column('HOSTNAME', style='cyan')
    table.add_column('STATUS', no_wrap=True)
    table.add_column('STORAGE / ERROR', overflow='fold')
    for row in rows:
        status = row['status']
        color = {'PENDING': 'yellow', 'SUCCESS': 'bright_green', 'ERROR': 'bright_red'}[status]
        table.add_row(row['name'], row['host'], f'[{color}]{status}[/{color}]', row['detail'])
    mode = 'ROOT FILESYSTEM ONLY' if root_only else 'ALL FILESYSTEMS'
    return Panel(table, title=f'[bold blue]{mode}[/bold blue]', border_style='bright_blue')


def choose_interactively(servers):
    CONSOLE.print('[bold bright_cyan]Available servers:[/bold bright_cyan] ' + ', '.join(s['name'] for s in servers))
    while True:
        entry = Prompt.ask('[cyan]Select server names (comma-separated), all, or exit[/cyan]', default='all').strip()
        if entry.lower() == 'exit':
            return None
        try:
            chosen = select_servers(servers, [] if entry.lower() == 'all' else entry.split(','))
        except ValueError as exc:
            CONSOLE.print(f'[bright_red]{exc}[/bright_red]')
            continue
        while True:
            answer = Prompt.ask('[yellow]Start monitoring? (yes/no/exit)[/yellow]', default='yes').strip().lower()
            if answer in ('yes', 'y'):
                return chosen
            if answer in ('exit', 'e'):
                return None
            if answer in ('no', 'n'):
                break
            CONSOLE.print('[bright_red]Enter yes, no, or exit.[/bright_red]')


def run_dashboard(servers, root_only=False, timeout=10, insecure=False, demo=False):
    rows = [dict(name=s['name'], host=s['host'], status='PENDING', detail='Waiting for SSH response...') for s in servers]
    failed = False
    with Live(dashboard(rows, root_only), console=CONSOLE, refresh_per_second=4, transient=False) as live:
        for index, server in enumerate(servers):
            try:
                if demo:
                    output = 'Filesystem Size Used Avail Use% Mounted on\n/dev/example 100G 45G 55G 45% /'
                else:
                    output = monitor(server, root_only, timeout, insecure)
                rows[index]['status'] = 'SUCCESS'
                rows[index]['detail'] = output or '(no output)'
                LOG.info('Disk check succeeded: %s', server['name'])
            except (paramiko.SSHException, OSError, ValueError, RuntimeError) as exc:
                failed = True
                rows[index]['status'] = 'ERROR'
                rows[index]['detail'] = type(exc).__name__ + ': ' + str(exc)
                LOG.warning('Disk check failed: %s (%s)', server['name'], type(exc).__name__)
            live.update(dashboard(rows, root_only), refresh=True)
    return 1 if failed else 0


def main(argv=None):
    parser = argparse.ArgumentParser(description='Interactive read-only SSH storage dashboard')
    parser.add_argument('--config', default='config.json')
    parser.add_argument('--servers', nargs='+', help='configured names; omit for interactive selection')
    parser.add_argument('--root-only', action='store_true')
    parser.add_argument('--timeout', type=int, default=10)
    parser.add_argument('--demo', action='store_true', help='display fictional data; no SSH connections')
    parser.add_argument('--insecure-auto-add-host-keys', action='store_true', help='LAB ONLY: trust unknown SSH keys')
    args = parser.parse_args(argv)
    if args.timeout <= 0:
        parser.error('--timeout must be positive')
    logging.basicConfig(filename='connection_logs.log', level=logging.INFO,
                        format='%(asctime)s %(levelname)s %(message)s')
    try:
        servers = load_servers(args.config)
        chosen = select_servers(servers, args.servers) if args.servers else choose_interactively(servers)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        CONSOLE.print(f'[bright_red]Configuration error: {exc}[/bright_red]')
        return 2
    if chosen is None:
        CONSOLE.print('[yellow]Exited without connecting.[/yellow]')
        return 0
    return run_dashboard(chosen, args.root_only, args.timeout, args.insecure_auto_add_host_keys, args.demo)


if __name__ == '__main__':
    raise SystemExit(main())
