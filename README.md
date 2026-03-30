# GSDeploy

GSDeploy is a desktop application for deploying, and monitoring game servers on virtual machines using Ansible and Docker.

It provides a simple GUI for managing infrastructure and deploying game servers without manual configuration.

---

## Features

- Set up existing virtual machines automatically using Ansible
- Deploy containerized game servers (Minecraft, Valheim)
- Integrated monitoring stack (Grafana, Prometheus, Loki)
- Real-time Docker log viewer per server
- GTK4 desktop interface

---

## System Requirements

### Control Machine (your computer)

- Ubuntu 22.04 or Debian 12
- Python 3.10+
- SSH access to target VMs

### Target VM

| Component | Minimum | Recommended |
|---|---|---|
| OS | Ubuntu 22.04 / Debian 12 | Ubuntu 22.04 LTS |
| CPU | 2 cores | 4 cores |
| RAM | 2 GB | 8 GB |
| Disk | 20 GB | 40 GB |

> **Note:** Do not create a separate `/home` partition. Game servers are installed
> under `/opt/gameservers/` — all disk space should be available to the root `/` partition.

### Per-Game Requirements

| Game | Min RAM | Min Disk |
|---|---|---|
| Minecraft | 2 GB | 5 GB |
| Valheim | 4 GB | 10 GB |

---

## Installation

### 1. Install system packages

```bash
sudo apt update && sudo apt install -y \
  ansible sshpass python3 python3-venv python3-gi \
  gir1.2-gtk-4.0 gir1.2-adw-1
```

### 2. Set up SSH key (if you don't have one)

```bash
ssh-keygen -t ed25519
```

### 3. Set up Python environment

> **Important:** Modern Ubuntu/Debian enforce PEP 668, which blocks global `pip install`.
> You must use a virtual environment. The `--system-site-packages` flag is required so
> GTK bindings are accessible inside the venv.

```bash
python3 -m venv venv --system-site-packages
source venv/bin/activate
pip install passlib
```

### 4. Install Ansible collections

```bash
ansible-galaxy collection install -r requirements.txt
```

### 5. Run GSDeploy

```bash
source venv/bin/activate
python3 -m gsdeploy.main
```

Application data is stored at `~/.local/share/gsdeploy/gsdeploy.db`.

---

## Usage

### 1. Add a VM

In the **Virtual Machines** tab, add a VM with:
- Display name and IP address
- Initial SSH user (the existing user on the VM, e.g. `ubuntu`)
- Admin username and password (the account GSDeploy will create)
- SSH key path (default: `~/.ssh/id_ed25519`)

### 2. Set up the VM

Click the provision button on the VM row. This connects to your existing VM via
password-based SSH, creates the admin user, installs Docker and monitoring agents,
then switches all future connections to use the admin user and your SSH key.

### 3. Deploy Monitoring

Click **Deploy Monitoring** on the VM. Only needs to be done once per monitoring VM.

Accessible at:
- Grafana: `http://<monitoring-ip>:3000`
- Prometheus: `http://<monitoring-ip>:9090`
- Loki: `http://<monitoring-ip>:3100`

### 4. Deploy Game Servers

Use **Deploy Server** to walk through a wizard — select a VM, choose a game,
configure settings, and deploy.

### 5. Manage Servers

The **Dashboard** shows all deployed servers. From there you can view live Docker
logs or remove a server from GSDeploy.

---

## Game Configuration

### Minecraft

| Field | Default | Description |
|---|---|---|
| Version | `LATEST` | Server version (e.g. `1.21.5`) |
| Memory | `2G` | RAM allocation |
| Game Mode | `survival` | `survival`, `creative`, `adventure` |
| Difficulty | `normal` | `peaceful`, `easy`, `normal`, `hard` |
| Max Players | `20` | Maximum concurrent players |

### Valheim

| Field | Default | Description |
|---|---|---|
| World Name | `Dedicated` | World save name |
| Server Password | `changeme` | Minimum 5 characters, cannot match world name |

---

## Game Server Data

Stored on the VM at `/opt/gameservers/<server-name>/`:

```
data/      — world data (Minecraft)
config/    — server configuration (Valheim)
mods/      — mods (Minecraft)
plugins/   — plugins (Minecraft)
world/     — world files (Minecraft)
```

---

## Monitoring Stack

| Component | Purpose | Port |
|---|---|---|
| Prometheus | Metrics collection | 9090 |
| Grafana | Dashboards | 3000 |
| Loki | Container log aggregation | 3100 |
| Node Exporter | VM system metrics | 9100 |
| cAdvisor | Container resource metrics | 8080 |
| Blackbox Exporter | TCP port probing | 9115 |
| mc-monitor | Minecraft server metrics | game port + 1000 |

---

## Troubleshooting

**`error: externally-managed-environment`**
Do not use `pip install` globally. Use the venv setup above.

**`No module named 'gi'`**
GTK bindings are missing or the venv was created without `--system-site-packages`:
```bash
sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1
rm -rf venv
python3 -m venv venv --system-site-packages
source venv/bin/activate
```

**`ansible: command not found`**
```bash
sudo apt install ansible
```

**SSH connection fails during provisioning**
- Verify the IP address is correct
- Confirm the initial SSH user exists on the VM
- Ensure the VM allows password-based SSH login initially
- Check the SSH key path is correct
