import os
import re
import shutil
import subprocess
import tempfile
import threading
from gi.repository import GLib

_APP_SHARE   = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
_USER_DATA   = os.path.expanduser("~/.local/share/gsdeploy")

PLAYBOOK_DIR = os.path.join(_APP_SHARE, "playbooks")
ANSIBLE_CFG  = os.path.join(_APP_SHARE, "ansible.cfg")
ROLES_PATH   = os.path.join(_APP_SHARE, "roles")
INVENTORY    = os.path.join(_USER_DATA, "hosts")
HOST_VARS    = os.path.join(_USER_DATA, "host_vars")


def _ansible_env():
    env = os.environ.copy()
    env["ANSIBLE_CONFIG"]     = ANSIBLE_CFG
    env["ANSIBLE_ROLES_PATH"] = ROLES_PATH
    return env

# Ensure user data dirs exist
os.makedirs(HOST_VARS, exist_ok=True)
# Seed inventory file if missing
if not os.path.exists(INVENTORY):
    _src = os.path.normpath(os.path.join(_APP_SHARE, "hosts"))
    if os.path.exists(_src):
        shutil.copy(_src, INVENTORY)
    else:
        with open(INVENTORY, "w") as _f:
            _f.write("[game_servers]\n\n[monitoring]\n")
# Always sync group_vars next to inventory so Ansible can find them
_gv_src = os.path.normpath(os.path.join(_APP_SHARE, "group_vars"))
_gv_dst = os.path.join(_USER_DATA, "group_vars")
if os.path.exists(_gv_src):
    if os.path.exists(_gv_dst):
        shutil.rmtree(_gv_dst)
    shutil.copytree(_gv_src, _gv_dst)


def sync_inventory_from_db():
    """Rebuild inventory and host_vars from the database, removing stale entries."""
    from gsdeploy.database import get_connection
    try:
        with get_connection() as conn:
            vms = conn.execute("SELECT * FROM vms").fetchall()
    except Exception:
        return

    # Rebuild inventory file from scratch
    game_hosts = [v for v in vms if v["vm_type"] != "monitoring"]
    mon_hosts  = [v for v in vms if v["vm_type"] == "monitoring"]

    lines = ["[game_servers]\n"]
    for v in game_hosts:
        lines.append(v["hostname"] + "\n")
    lines.append("\n[monitoring]\n")
    for v in mon_hosts:
        lines.append(v["hostname"] + "\n")

    with open(INVENTORY, "w") as f:
        f.writelines(lines)

    # Remove stale host_vars files
    known = {v["hostname"] for v in vms}
    if os.path.isdir(HOST_VARS):
        for fname in os.listdir(HOST_VARS):
            hostname = fname.replace(".yaml", "")
            if hostname not in known:
                os.remove(os.path.join(HOST_VARS, fname))

    # Write host_vars for all VMs
    for v in vms:
        path = os.path.join(HOST_VARS, f"{v['hostname']}.yaml")
        with open(path, "w") as f:
            f.write(f"---\nansible_host: \"{v['ip']}\"\nansible_user: {v['ssh_user']}\nansible_ssh_private_key_file: {v['ssh_key']}\n")


# ── Inventory management ─────────────────────────────────────────────────────

def add_to_inventory(hostname, ip, ssh_user, ssh_key, vm_type):
    """Add a host to the Ansible inventory and create its host_vars file."""
    group = "monitoring" if vm_type == "monitoring" else "game_servers"

    host_vars_path = os.path.join(HOST_VARS, f"{hostname}.yaml")
    with open(host_vars_path, "w") as f:
        f.write(f"---\nansible_host: \"{ip}\"\nansible_user: {ssh_user}\nansible_ssh_private_key_file: {ssh_key}\n")

    with open(INVENTORY, "r") as f:
        content = f.read()

    if re.search(rf"^\s*{re.escape(hostname)}\s*$", content, re.MULTILINE):
        return  # already present

    pattern = rf"(\[{re.escape(group)}\][^\[]*)"
    match = re.search(pattern, content, re.DOTALL)
    if match:
        block = match.group(1).rstrip("\n")
        new_block = block + f"\n{hostname}\n"
        content = content[:match.start()] + new_block + content[match.end():]
    else:
        content += f"\n[{group}]\n{hostname}\n"

    with open(INVENTORY, "w") as f:
        f.write(content)


def remove_from_inventory(hostname):
    """Remove a host from the Ansible inventory and delete its host_vars file."""
    host_vars_path = os.path.join(HOST_VARS, f"{hostname}.yaml")
    if os.path.exists(host_vars_path):
        os.remove(host_vars_path)

    with open(INVENTORY, "r") as f:
        lines = f.readlines()

    filtered = [l for l in lines if l.strip() != hostname]

    with open(INVENTORY, "w") as f:
        f.writelines(filtered)


def _get_monitoring_ip():
    """Get the monitoring VM's IP from the database."""
    from gsdeploy.database import get_connection
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT ip FROM vms WHERE vm_type = 'monitoring' LIMIT 1"
            ).fetchone()
            return row["ip"] if row else ""
    except Exception:
        return ""


def _debug_flag():
    from gsdeploy.database import get_setting
    return ["-v"] if get_setting("ansible_debug", "0") == "1" else []


def _run_playbook(cmd, env, become_pass, log_callback, done_callback):
    """
    Run an Ansible playbook in a background thread, streaming output.
    Returns a cancel() function that kills the process.
    """
    proc_ref = [None]

    def _run():
        with tempfile.NamedTemporaryFile(mode="w", suffix=".pass", delete=False) as tf:
            tf.write(become_pass + "\n")
            tf_path = tf.name
        try:
            proc = subprocess.Popen(
                cmd + _debug_flag() + ["-i", INVENTORY, "--become-password-file", tf_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=env,
            )
            proc_ref[0] = proc
            for line in proc.stdout:
                GLib.idle_add(log_callback, line)
            proc.wait()
            GLib.idle_add(done_callback, proc.returncode == 0)
        except Exception as e:
            GLib.idle_add(log_callback, f"ERROR: {e}\n")
            GLib.idle_add(done_callback, False)
        finally:
            os.unlink(tf_path)

    threading.Thread(target=_run, daemon=True).start()

    def cancel():
        if proc_ref[0] and proc_ref[0].poll() is None:
            proc_ref[0].kill()

    return cancel


def _get_monitoring_become_pass():
    """Get the monitoring VM's admin password from the database."""
    from gsdeploy.database import get_connection
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT admin_password FROM vms WHERE vm_type = 'monitoring' LIMIT 1"
            ).fetchone()
            return row["admin_password"] if row else ""
    except Exception:
        return ""


def run_deploy_gameserver(vm_name, game_type, server_name, port, admin_username,
                          extra_vars, become_pass, log_callback, done_callback):
    """
    Run deploy_gameserver.yml in a background thread.
    Returns a cancel() function that kills the process.
    """
    extra = {
        "target":            vm_name,
        "game_type":         game_type,
        "server_name":       server_name,
        "server_port":       str(port),
        "admin_username":    admin_username,
        "monitoring_host_ip": _get_monitoring_ip(),
    }
    extra.update(extra_vars)

    # Pass monitoring VM's become password via extra vars so Ansible can sudo on it
    monitoring_become = _get_monitoring_become_pass()
    if monitoring_become:
        extra["monitoring_become_pass"] = monitoring_become

    env = _ansible_env()
    cmd = ["ansible-playbook", os.path.join(PLAYBOOK_DIR, "deploy_gameserver.yml")]
    for k, v in extra.items():
        cmd += ["-e", f"{k}={v}"]

    return _run_playbook(cmd, env, become_pass, log_callback, done_callback)


def run_provision_vm(hostname, ip, initial_user, initial_ssh_pass, admin_username, admin_password,
                     deployer_ssh_key, log_callback, done_callback):
    """
    Run provision_vm.yml in a background thread.
    Returns a cancel() function that kills the process.
    """
    env = _ansible_env()
    proc_ref = [None]

    monitoring_ip = _get_monitoring_ip()

    def _run():
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as tf:
            tf.write(f"initial_ssh_pass: '{initial_ssh_pass}'\n")
            tf.write(f"initial_become_pass: '{initial_ssh_pass}'\n")
            if admin_password:
                tf.write(f"admin_password: '{admin_password}'\n")
            tf_path = tf.name
        try:
            cmd = [
                "ansible-playbook",
                os.path.join(PLAYBOOK_DIR, "provision_vm.yml"),
                "-i", INVENTORY,
                "-i", f"{ip},",
                "-e", (f"target={ip} initial_user={initial_user} "
                       f"admin_username={admin_username} deployer_ssh_key={deployer_ssh_key} "
                       f"monitoring_host_ip={monitoring_ip}"),
                "-e", f"@{tf_path}",
            ] + _debug_flag()
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    text=True, env=env)
            proc_ref[0] = proc
            for line in proc.stdout:
                GLib.idle_add(log_callback, line)
            proc.wait()
            GLib.idle_add(done_callback, proc.returncode == 0)
        except Exception as e:
            GLib.idle_add(log_callback, f"ERROR: {e}\n")
            GLib.idle_add(done_callback, False)
        finally:
            os.unlink(tf_path)

    threading.Thread(target=_run, daemon=True).start()

    def cancel():
        if proc_ref[0] and proc_ref[0].poll() is None:
            proc_ref[0].kill()

    return cancel


def run_remove_gameserver(vm_name, server_name, become_pass, log_callback, done_callback):
    """
    Run remove_gameserver.yml in a background thread.
    Stops and removes the container but leaves data directories intact.
    """
    env = _ansible_env()
    cmd = [
        "ansible-playbook",
        os.path.join(PLAYBOOK_DIR, "remove_gameserver.yml"),
        "-e", f"target={vm_name}",
        "-e", f"server_name={server_name}",
    ]
    return _run_playbook(cmd, env, become_pass, log_callback, done_callback)


def docker_action(ip, ssh_user, ssh_key, admin_password, container, action, done_callback, game_type=None):
    """
    Run `docker start` or `docker stop` on a remote container over SSH.
    action: "start" or "stop"
    """
    import shlex

    def _run():
        key = os.path.expanduser(ssh_key)
        main = shlex.quote(container)
        has_monitor = game_type == "minecraft"
        monitor = shlex.quote(container + "_monitor")
        if action == "stop":
            if has_monitor:
                remote_cmd = (
                    f"echo {shlex.quote(admin_password)} | sudo -S sh -c "
                    f"'docker stop --time 2 {monitor} 2>/dev/null; docker stop --time 60 {main}'"
                )
            else:
                remote_cmd = (
                    f"echo {shlex.quote(admin_password)} | sudo -S sh -c "
                    f"'docker stop --time 60 {main}'"
                )
        else:
            if has_monitor:
                remote_cmd = (
                    f"echo {shlex.quote(admin_password)} | sudo -S sh -c "
                    f"'docker start {main} {monitor}'"
                )
            else:
                remote_cmd = (
                    f"echo {shlex.quote(admin_password)} | sudo -S sh -c "
                    f"'docker start {main}'"
                )
        cmd = [
            "ssh", "-i", key,
            "-o", "StrictHostKeyChecking=accept-new",
            "-o", "BatchMode=yes",
            "-o", "ServerAliveInterval=10",
            "-o", "ServerAliveCountMax=12",
            f"{ssh_user}@{ip}",
            remote_cmd,
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if proc.returncode == 0:
                GLib.idle_add(done_callback, True, None)
            else:
                error = (proc.stderr.strip() or proc.stdout.strip() or
                         f"exit code {proc.returncode}")
                GLib.idle_add(done_callback, False, error)
        except subprocess.TimeoutExpired:
            GLib.idle_add(done_callback, False, "Timed out waiting for response")
        except Exception as e:
            GLib.idle_add(done_callback, False, str(e))

    threading.Thread(target=_run, daemon=True).start()


def get_container_status(ip, ssh_user, ssh_key, admin_password, container, done_callback):
    """
    Returns the container status string ("running", "exited", etc.) via done_callback,
    or None if the container doesn't exist or SSH fails.
    """
    import shlex

    def _run():
        key = os.path.expanduser(ssh_key)
        remote_cmd = (
            f"echo {shlex.quote(admin_password)} | sudo -S "
            f"docker inspect --format={{{{.State.Status}}}} {shlex.quote(container)} 2>/dev/null"
        )
        cmd = [
            "ssh", "-i", key,
            "-o", "StrictHostKeyChecking=accept-new",
            "-o", "BatchMode=yes",
            f"{ssh_user}@{ip}",
            remote_cmd,
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True)
            status = proc.stdout.strip() if proc.returncode == 0 else None
            GLib.idle_add(done_callback, status)
        except Exception:
            GLib.idle_add(done_callback, None)

    threading.Thread(target=_run, daemon=True).start()


def stream_docker_logs(ip, ssh_user, ssh_key, admin_password, container, log_callback, done_callback):
    """
    Stream `docker logs -f -t <container>` from a remote VM over SSH.
    Returns a cancel() function that kills the SSH process.
    """
    import shlex
    proc_ref = [None]

    def _run():
        key = os.path.expanduser(ssh_key)
        remote_cmd = f"echo {shlex.quote(admin_password)} | sudo -S docker logs -f -t {shlex.quote(container)}"
        cmd = [
            "ssh", "-i", key,
            "-o", "StrictHostKeyChecking=accept-new",
            "-o", "BatchMode=yes",
            f"{ssh_user}@{ip}",
            remote_cmd,
        ]
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            proc_ref[0] = proc
            for line in proc.stdout:
                if not line.startswith("[sudo]"):
                    GLib.idle_add(log_callback, line)
            proc.wait()
            if proc.returncode not in (0, -9):  # -9 = killed intentionally
                GLib.idle_add(done_callback, False)
            else:
                GLib.idle_add(done_callback, True)
        except Exception as e:
            GLib.idle_add(log_callback, f"ERROR: {e}\n")
            GLib.idle_add(done_callback, False)

    threading.Thread(target=_run, daemon=True).start()

    def cancel():
        if proc_ref[0] and proc_ref[0].poll() is None:
            proc_ref[0].kill()

    return cancel


def transfer_files(local_path, ip, ssh_user, ssh_key, remote_dest,
                   log_callback, done_callback):
    """
    Transfer a local file or directory to remote_dest on the VM using rsync over SSH.
    Returns a cancel() function.
    """
    proc_ref = [None]

    def _run():
        key = os.path.expanduser(ssh_key)
        # Ensure trailing slash on source dir so rsync copies contents, not the folder itself
        src = local_path.rstrip("/") + "/" if os.path.isdir(local_path) else local_path
        cmd = [
            "rsync", "-avz", "--progress",
            "-e", f"ssh -i {key} -o StrictHostKeyChecking=accept-new -o BatchMode=yes",
            src,
            f"{ssh_user}@{ip}:{remote_dest}",
        ]
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            proc_ref[0] = proc
            for line in proc.stdout:
                GLib.idle_add(log_callback, line)
            proc.wait()
            GLib.idle_add(done_callback, proc.returncode == 0)
        except Exception as e:
            GLib.idle_add(log_callback, f"ERROR: {e}\n")
            GLib.idle_add(done_callback, False)

    threading.Thread(target=_run, daemon=True).start()

    def cancel():
        if proc_ref[0] and proc_ref[0].poll() is None:
            proc_ref[0].kill()

    return cancel


def get_public_ip(ip, ssh_user, ssh_key, done_callback):
    """
    SSH into the VM and run `curl -s ifconfig.me` to get its public IP.
    Calls done_callback(ip_string) on the main thread, or done_callback(None) on failure.
    """
    def _run():
        key = os.path.expanduser(ssh_key)
        cmd = [
            "ssh", "-i", key,
            "-o", "StrictHostKeyChecking=accept-new",
            "-o", "BatchMode=yes",
            "-o", "ConnectTimeout=10",
            f"{ssh_user}@{ip}",
            "curl -s --max-time 10 ifconfig.me",
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
            result = proc.stdout.strip() if proc.returncode == 0 and proc.stdout.strip() else None
            GLib.idle_add(done_callback, result)
        except Exception:
            GLib.idle_add(done_callback, None)

    threading.Thread(target=_run, daemon=True).start()


def check_connection(ip, ssh_user, ssh_key, done_callback, initial_user=None, initial_pass=None):
    """
    Test reachability of a VM by pinging its IP.
    Calls done_callback(True) if reachable, done_callback(False) otherwise.
    """
    def _run():
        try:
            proc = subprocess.run(
                ["ping", "-c", "1", "-W", "3", ip],
                capture_output=True, timeout=10
            )
            GLib.idle_add(done_callback, proc.returncode == 0)
        except Exception:
            GLib.idle_add(done_callback, False)

    threading.Thread(target=_run, daemon=True).start()


def open_terminal(cmd_args):
    """
    Launch a terminal emulator running cmd_args.
    Returns True if a supported terminal was found, False otherwise.
    """
    import shutil
    import shlex

    bash_cmd = " ".join(shlex.quote(a) for a in cmd_args) + "; exec bash"

    terminals = [
        ("gnome-terminal", ["gnome-terminal", "--", "bash", "-c", bash_cmd]),
        ("xterm",          ["xterm", "-e", "bash", "-c", bash_cmd]),
        ("konsole",        ["konsole", "-e", "bash", "-c", bash_cmd]),
        ("xfce4-terminal", ["xfce4-terminal", "-e", f"bash -c {shlex.quote(bash_cmd)}"]),
        ("alacritty",      ["alacritty", "-e", "bash", "-c", bash_cmd]),
        ("kitty",          ["kitty", "bash", "-c", bash_cmd]),
        ("tilix",          ["tilix", "-e", "bash", "-c", bash_cmd]),
        ("wezterm",        ["wezterm", "start", "--", "bash", "-c", bash_cmd]),
    ]

    for name, launch_cmd in terminals:
        if shutil.which(name):
            subprocess.Popen(launch_cmd)
            return True
    return False


def run_deploy_monitoring(vm_name, become_pass, log_callback, done_callback):
    """
    Run deploy_monitoring.yml in a background thread, targeting vm_name.
    Returns a cancel() function that kills the process.
    """
    env = _ansible_env()
    monitoring_ip = _get_monitoring_ip()
    cmd = [
        "ansible-playbook",
        os.path.join(PLAYBOOK_DIR, "deploy_monitoring.yml"),
        "-e", f"target={vm_name}",
        "-e", f"monitoring_host_ip={monitoring_ip}",
    ]
    return _run_playbook(cmd, env, become_pass, log_callback, done_callback)
