import os
import re
import subprocess
import tempfile
import threading
from gi.repository import GLib

PLAYBOOK_DIR = os.path.join(os.path.dirname(__file__), "..", "playbooks")
INVENTORY    = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "hosts"))
HOST_VARS    = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "host_vars"))
ANSIBLE_CFG  = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))


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


def run_deploy_gameserver(vm_name, game_type, server_name, port, extra_vars,
                          become_pass, log_callback, done_callback):
    """
    Run deploy_gameserver.yml in a background thread.
    Streams stdout/stderr line by line via log_callback (called on GTK main loop).
    Calls done_callback(success: bool) when finished.
    """
    extra = {
        "target":      vm_name,
        "game_type":   game_type,
        "server_name": server_name,
        "server_port": str(port),
    }
    extra.update(extra_vars)

    env = os.environ.copy()
    env["ANSIBLE_CONFIG"] = os.path.join(ANSIBLE_CFG, "ansible.cfg")

    def _run():
        with tempfile.NamedTemporaryFile(mode="w", suffix=".pass", delete=False) as tf:
            tf.write(become_pass + "\n")
            tf_path = tf.name
        try:
            cmd = ["ansible-playbook", os.path.join(PLAYBOOK_DIR, "deploy_gameserver.yml")]
            for k, v in extra.items():
                cmd += ["-e", f"{k}={v}"]
            cmd += ["--become-password-file", tf_path]
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=env,
            )
            for line in proc.stdout:
                GLib.idle_add(log_callback, line)

            proc.wait()
            success = proc.returncode == 0
            GLib.idle_add(done_callback, success)

        except Exception as e:
            GLib.idle_add(log_callback, f"ERROR: {e}\n")
            GLib.idle_add(done_callback, False)
        finally:
            os.unlink(tf_path)

    threading.Thread(target=_run, daemon=True).start()


def run_provision_vm(hostname, initial_user, initial_ssh_pass, admin_username, admin_password,
                     deployer_ssh_key, log_callback, done_callback):
    """
    Run provision_vm.yml in a background thread.
    Calls done_callback(success: bool) when finished.
    """
    env = os.environ.copy()
    env["ANSIBLE_CONFIG"] = os.path.join(ANSIBLE_CFG, "ansible.cfg")

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
                "-e", (f"target={hostname} initial_user={initial_user} "
                       f"admin_username={admin_username} deployer_ssh_key={deployer_ssh_key}"),
                "-e", f"@{tf_path}",
            ]
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=env,
            )
            for line in proc.stdout:
                GLib.idle_add(log_callback, line)

            proc.wait()
            success = proc.returncode == 0
            GLib.idle_add(done_callback, success)

        except Exception as e:
            GLib.idle_add(log_callback, f"ERROR: {e}\n")
            GLib.idle_add(done_callback, False)
        finally:
            os.unlink(tf_path)

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
            "-o", "StrictHostKeyChecking=no",
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


def run_deploy_monitoring(vm_name, become_pass, log_callback, done_callback):
    """
    Run deploy_monitoring.yml in a background thread, targeting vm_name.
    Streams stdout/stderr line by line via log_callback (called on GTK main loop).
    Calls done_callback(success: bool) when finished.
    """
    env = os.environ.copy()
    env["ANSIBLE_CONFIG"] = os.path.join(ANSIBLE_CFG, "ansible.cfg")

    def _run():
        with tempfile.NamedTemporaryFile(mode="w", suffix=".pass", delete=False) as tf:
            tf.write(become_pass + "\n")
            tf_path = tf.name
        try:
            cmd = [
                "ansible-playbook",
                os.path.join(PLAYBOOK_DIR, "deploy_monitoring.yml"),
                "-e", f"target={vm_name}",
                "--become-password-file", tf_path,
            ]
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=env,
            )
            for line in proc.stdout:
                GLib.idle_add(log_callback, line)

            proc.wait()
            success = proc.returncode == 0
            GLib.idle_add(done_callback, success)

        except Exception as e:
            GLib.idle_add(log_callback, f"ERROR: {e}\n")
            GLib.idle_add(done_callback, False)
        finally:
            os.unlink(tf_path)

    threading.Thread(target=_run, daemon=True).start()
