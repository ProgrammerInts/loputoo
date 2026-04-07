# GSDeploy

GSDeploy is a desktop application for deploying and monitoring game servers on virtual machines using Ansible and Docker.

It provides a simple GUI for managing infrastructure and deploying game servers without manual configuration.

### How it works

GSDeploy runs on **your computer** and connects to a remote VM over SSH. It configures the VM, deploys game servers as Docker containers, and sets up a monitoring stack — all without manual server configuration.

```
Your computer               Gameserver VM
┌─────────────┐           ┌──────────────────┐
│             │           │   Minecraft      │
│  GSDeploy  ─┼──── SSH ─►│   Valheim        │
│             │           │   ...            │
└──────┬──────┘           └──────────────────┘
       │
       │                  Monitoring VM (optional)
       │                  ┌──────────────────┐
       └──── SSH ─────────►   Grafana        │
                          │   Prometheus     │
                          │   Loki           │
                          └──────────────────┘
```

> **Tip:** Monitoring is optional. It can run on the same VM as your game servers, but a
> **separate VM is recommended** so monitoring does not compete for resources with your games.

---

## Features

- Provision existing virtual machines automatically using Ansible
- Deploy containerized game servers (Minecraft, Valheim, Vintage Story, Factorio)
- Modded Minecraft support (Forge, Fabric, Paper, and others via itzg/minecraft-server)
- Transfer mods, plugins and maps to your game server from your local machine
- Integrated monitoring stack (Grafana, Prometheus, Loki)
- Real-time Docker log viewer per server
- GTK4 desktop interface

---

## System Requirements

### Control Machine (your computer)

- Ubuntu 24.04 LTS or newer
- Linux Mint 22 or newer
- Python 3.10+
- SSH access to target VMs

> **Note:** Requires libadwaita 1.4+. Ubuntu 22.04/23.04 and Debian 12 ship older versions and are not supported.
> WSL2 is not recommended — GTK4 GUI support is limited.

> **Security recommendation:** Use a passphrase-protected SSH key to prevent unauthorized VM access
> if your computer is compromised:
> ```bash
> ssh-keygen -p -f ~/.ssh/id_ed25519
> ```
> Use `ssh-agent` or your desktop keyring to cache the passphrase for the session.

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
| Minecraft (vanilla) | 2 GB | 5 GB |
| Minecraft (modded) | 4 GB | 10 GB |
| Valheim | 4 GB | 10 GB |
| Vintage Story | 2 GB | 5 GB |
| Factorio | 1 GB | 5 GB |

---

## Installation

### Option A — Install from .deb package (recommended)

Download the latest `.deb` from [GitHub Releases](../../releases/latest), then:

```bash
sudo apt install ./gsdeploy_1.0.0.deb
```

Launch from your application menu or run `gsdeploy` in a terminal.

### Option B — Run from source

#### 1. Install system packages

```bash
sudo apt update && sudo apt install -y \
  git ansible sshpass python3 python3-venv python3-gi \
  gir1.2-gtk-4.0 gir1.2-adw-1
```

#### 2. Clone the repository

```bash
git clone https://github.com/indrekis/loputoo.git
cd loputoo
```

#### 3. Set up SSH key (if you don't have one)

GSDeploy uses SSH key authentication to connect to your VMs. If you don't have a key yet:

```bash
ssh-keygen -t ed25519
```

This creates a key pair at `~/.ssh/id_ed25519` (private) and `~/.ssh/id_ed25519.pub` (public).
The public key is automatically copied to the VM during provisioning — you don't need to do anything manually.

> See [this SSH key guide](https://www.ssh.com/academy/ssh/keygen) for more detail.

#### 4. Set up Python environment

> **Important:** Modern Ubuntu/Debian enforce PEP 668, which blocks global `pip install`.
> You must use a virtual environment. The `--system-site-packages` flag is required so
> GTK bindings are accessible inside the venv.

```bash
python3 -m venv gsdeploy-venv --system-site-packages
source gsdeploy-venv/bin/activate
pip install passlib
```

#### 5. Install Ansible collections

```bash
ansible-galaxy collection install -r requirements.txt
```

#### 6. Run GSDeploy

```bash
source gsdeploy-venv/bin/activate
python3 -m gsdeploy.main
```

Application data is stored at `~/.local/share/gsdeploy/`.

---

## Usage

### 1. Add a VM

In the **Virtual Machines** tab, add a VM with:
- Display name and IP address
- Initial SSH user (the existing user on the VM, e.g. `ubuntu`)
- Admin username and password (the account GSDeploy will create)
- SSH key path (default: `~/.ssh/id_ed25519`)
- VM type: **Game Server** or **Monitoring**

> Only one Monitoring VM is supported at a time.

### 2. Provision the VM

Click the provision button on the VM row. This connects to your existing VM via
password-based SSH, creates the admin user, installs Docker and monitoring agents,
then switches all future connections to use the admin user and your SSH key.

### 3. Deploy Monitoring (optional)

Click **Deploy Monitoring** on the monitoring VM row. Only needs to be done once per monitoring VM.

If a monitoring VM is configured, promtail (log shipping) and metrics exporters are automatically
set up on game server VMs during provisioning.

Accessible at:
- Grafana: `http://<monitoring-ip>:3000`
- Prometheus: `http://<monitoring-ip>:9090`
- Loki: `http://<monitoring-ip>:3100`

### 4. Deploy Game Servers

Use the **Deploy** tab to walk through a wizard — select a VM, choose a game,
configure settings, and deploy.

### 5. Manage Servers

The **Dashboard** shows all deployed servers. From there you can start/stop containers,
view live Docker logs, view the deployment config, or remove a server.

### 6. Transfer Mods and Maps

Use the **Modifications** tab to transfer mods, plugins, or map files from your local machine
to a game server VM using rsync over SSH.

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
| Server Type | `VANILLA` | `VANILLA`, `FORGE`, `FABRIC`, `PAPER`, etc. |

> For modded servers (Forge, Fabric): place mods in the **Modifications** tab after deployment,
> then restart the server from the Dashboard.

### Valheim

| Field | Default | Description |
|---|---|---|
| World Name | `Dedicated` | World save name |
| Server Password | `changeme` | Minimum 5 characters, cannot match world name |

### Vintage Story

| Field | Default | Description |
|---|---|---|
| Version | `latest` | Server version |
| Game Port | `42420` | Port players connect to |

### Factorio

| Field | Default | Description |
|---|---|---|
| Version | `latest` | Server version |
| Game Port | `34197` | UDP port players connect to |

---

## Game Server Data

Stored on the VM at `/opt/gameservers/<server-name>/`:

```
data/      — world data and server files
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
| Promtail | Log shipping to Loki | — |
| mc-monitor | Minecraft server metrics | game port + 1000 |

> **Security warning:** Prometheus (9090), Loki (3100), and the exporter ports (9100, 8080) have no
> authentication. If your VM has a public IP, restrict these ports to your IP only using
> the VM's firewall or cloud security group rules. Grafana (3000) is safe to expose as it
> has login protection.

---

## Using VMs on a Different Network

GSDeploy works with any IP address — local, VPN, or public. Enter the VM's reachable IP
when adding it and SSH access is all that is needed for provisioning and deployment.

**Cloud VPS / public IP**
- SSH (port 22) must be open from your machine
- Game ports must be open for players to connect (GSDeploy opens them in UFW on the VM,
  but your cloud provider's firewall/security group also needs to allow them)
- **Firewall the monitoring ports** (9090, 3100, 9100, 8080) — they have no authentication
  and must not be publicly accessible

**VMs behind NAT (different LAN / home router)**
- Forward port 22 on the router to the VM for SSH access during provisioning/deployment
- Forward the game port(s) for players to connect

**VPN (e.g. Tailscale, WireGuard)**
- Assign VMs a VPN IP and use that — no port forwarding needed, monitoring ports stay private

---

## Troubleshooting

**`error: externally-managed-environment`**
Do not use `pip install` globally. Use the venv setup in Option B above.

**`No module named 'gi'`**
GTK bindings are missing or the venv was created without `--system-site-packages`:
```bash
sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1
rm -rf gsdeploy-venv
python3 -m venv gsdeploy-venv --system-site-packages
source gsdeploy-venv/bin/activate
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
