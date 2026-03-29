# GSDeploy

Ansible-based tool for deploying and monitoring game servers on self-hosted VMs.
Designed to be managed via the GSDeploy desktop application (in development).

---

## Requirements

### Control Machine (where you run Ansible)
- Ansible
- Python 3 + `passlib` (`pip install passlib`)
- `sshpass` (`sudo apt install sshpass`)
- SSH key pair at `~/.ssh/id_ed25519`

Install Ansible collections:
```bash
ansible-galaxy collection install -r requirements.txt
```

### VM Requirements

| Component | Minimum | Recommended |
|---|---|---|
| OS | Ubuntu 22.04 / Debian 12 | Ubuntu 22.04 LTS |
| CPU | 2 cores | 4 cores |
| RAM | 2GB | 8GB |
| Disk | 20GB | 40GB |

> **Important:** Do not create a separate `/home` partition. Game servers are installed
> under `/opt/gameservers/` — all disk space should be available to the root `/` partition.

### Per-Game Requirements

| Game | Min RAM | Min Disk |
|---|---|---|
| Minecraft | 2GB | 5GB |
| Valheim | 4GB | 10GB |

---

## VM Setup

### 1. Bootstrap a new VM

Connects as your existing sudo user, creates a temporary install user, sets up a
permanent admin user with Docker and monitoring agents, then removes the install user.

```bash
ansible-playbook playbooks/provision_vm.yml \
  -e "target=<hostname> initial_user=<user> admin_username=<admin>" \
  --ask-pass \
  -e "initial_become_pass=$(read -sp 'Become password: ' p && echo $p)"
```

Admin credentials are displayed at the end and saved to `~/Documents/gsdeploy_credentials.txt`.

### 2. Add VM to inventory

Add the hostname to `hosts` under the appropriate group, and create a `host_vars/<hostname>.yaml`:

```yaml
ansible_host: "192.168.0.x"
ansible_user: <admin_username>
ansible_ssh_private_key_file: ~/.ssh/id_ed25519
```

---

## Monitoring

Deploy Prometheus, Loki, and Grafana on a dedicated monitoring VM:

```bash
ansible-playbook playbooks/deploy_monitoring.yml
```

Accessible at:
- Grafana: `http://<monitoring-ip>:3000`
- Prometheus: `http://<monitoring-ip>:9090`
- Loki: `http://<monitoring-ip>:3100`

---

## Deploying Game Servers

```bash
ansible-playbook playbooks/deploy_gameserver.yml \
  -e "target=<hostname> game_type=<game> name=<server-name> port=<port>" \
  --ask-become-pass
```

### Minecraft

| Variable | Default | Description |
|---|---|---|
| `minecraft_version` | `LATEST` | Server version (e.g. `1.21.1`) |
| `minecraft_memory` | `2G` | RAM allocation |
| `minecraft_difficulty` | `normal` | `peaceful`, `easy`, `normal`, `hard` |
| `minecraft_max_players` | `20` | Max players |
| `minecraft_motd` | server name | Message of the day |
| `minecraft_seed` | random | World seed |
| `minecraft_mode` | `survival` | `survival`, `creative`, `adventure` |

Example:
```bash
ansible-playbook playbooks/deploy_gameserver.yml \
  -e "target=gamevm game_type=minecraft name=survival port=25565 minecraft_version=1.21.1" \
  --ask-become-pass
```

### Valheim

| Variable | Default | Description |
|---|---|---|
| `valheim_server_name` | server name | Name shown in server browser |
| `valheim_world_name` | `Dedicated` | World name |
| `valheim_server_pass` | `changeme` | Server password |
| `valheim_public` | `true` | Show in public server list |

Example:
```bash
ansible-playbook playbooks/deploy_gameserver.yml \
  -e "target=gamevm game_type=valheim name=myvalheim port=2456 valheim_server_pass=secret" \
  --ask-become-pass
```

---

## Game Server Data

Game server files are stored on the VM at:
```
/opt/gameservers/<server-name>/
  data/    — world data
  config/  — server configuration
```
