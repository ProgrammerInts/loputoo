# GSDeploy

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![Ansible](https://img.shields.io/badge/Ansible-automation-red)
![Docker](https://img.shields.io/badge/Docker-containers-2496ED)
![GTK4](https://img.shields.io/badge/GTK4-libadwaita-4A90D9)
![License](https://img.shields.io/badge/License-GPL%20v3-green)

> **Homelab project:** GSDeploy is designed for home networks behind NAT — running game servers on your own hardware or local VMs. It can work with cloud VPS providers, but requires careful firewall configuration. It is not intended for production environments or large-scale deployments.

GSDeploy is a desktop application for deploying and monitoring game servers on remote machines using Ansible and Docker. The target machine can be a virtual machine, a physical server, a repurposed PC, or a cloud VPS — anything running a supported Linux OS with SSH access.

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

> **Credits:** Game server containers are powered by community-maintained Docker images:
> [itzg/minecraft-server](https://github.com/itzg/docker-minecraft-server),
> [lloesche/valheim-server](https://github.com/lloesche/valheim-server-docker),
> [quartzar/vintage-story-server](https://hub.docker.com/r/quartzar/vintage-story-server),
> [factoriotools/factorio](https://github.com/factoriotools/factorio-docker).

---

## System Requirements

### Control Machine (your computer)

- Ubuntu 24.04 LTS or newer
- Linux Mint 22 or newer
- Python 3.10+
- SSH access to target VMs
- ~350 MB disk space (installed)
- ~50 MB RAM at idle, up to ~150 MB during provisioning/deployment (rough estimates)

> **Note:** Requires libadwaita 1.4+. Ubuntu 22.04/23.04 and Debian 12 ship older versions and are not supported.
> WSL2 is not recommended — GTK4 GUI support is limited.

> **Security recommendation:** Use a passphrase-protected SSH key to prevent unauthorized VM access
> if your computer is compromised (use this if you wish to change passphrase of current key):
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

> **Local VM networking:** When using VMware or VirtualBox, set the VM network adapter to **Bridged** mode. This gives the VM its own IP on your local network, making it directly reachable from GSDeploy without any port forwarding. Network adapter's NAT mode requires additional port forwarding configuration and is not recommended.

### Per-Game Requirements

| Game | Min RAM | Min Disk |
|---|---|---|
| Minecraft (vanilla) | 2 GB | 5 GB |
| Minecraft (modded) | 4 GB | 10 GB |
| Valheim | 4 GB | 10 GB |
| Vintage Story | 2 GB | 5 GB |
| Factorio | 1 GB | 5 GB |

---

## Using VMs on a Different Network

> **Design assumption:** GSDeploy is designed for home networks behind NAT, where the local network is trusted and monitoring ports are not reachable from the internet. The provisioning process configures UFW to deny all incoming traffic except SSH, game ports, and monitoring ports — but this only protects the VM itself. If your VM is on a cloud provider (Hetzner, AWS, etc.) without additional firewall rules, monitoring ports with no authentication or TLS could be exposed to the internet. **Always configure your cloud provider's firewall in addition to UFW.**

GSDeploy works with any IPv4 address — local, VPN, or public. Enter the VM's reachable IP
when adding it and SSH access is all that is needed for provisioning and deployment. IPv6 is not currently supported.

**Cloud VPS / public IP (Hetzner, AWS, DigitalOcean, etc.)**

Cloud providers have their own firewall layer **on top of** UFW. GSDeploy configures UFW on the VM, but you must also open the same ports in your cloud provider's firewall (Hetzner Firewall, AWS Security Groups, etc.) — UFW alone is not enough.

| Port | Open to | Reason |
|---|---|---|
| 22 | Your IP only | SSH for provisioning and deployment |
| Game port (e.g. 25565) | Everyone | Players connecting to the server |
| 3000 | Your IP only | Grafana (if you need remote access) |
| 9090, 3100, 9100, 8080 | Nobody | No authentication — never expose publicly |

> **Note:** If your home IP changes, you will need to update the SSH rule in the cloud firewall before you can provision or deploy again.

> **Grafana over public internet:** Grafana runs plain HTTP with no TLS — credentials travel unencrypted. Restrict it to your IP only, or put a reverse proxy (e.g. nginx + Let's Encrypt) in front of it if broader access is needed.

**VMs behind NAT (different LAN / home router)**
- Forward port 22 on the router to the VM for SSH access during provisioning/deployment
- Forward the game port(s) for players to connect

**VPN (e.g. Tailscale, WireGuard)**
- Assign VMs a VPN IP and use that — no port forwarding needed, monitoring ports stay private

---

## Installation

### Option A — Install from .deb package (recommended)

Download the latest `.deb` from [GitHub Releases](../../releases/latest), then:

```bash
sudo apt install ./gsdeploy_X.X.X.deb
```

Launch from your application menu or run `gsdeploy` in a terminal.

> Make sure you have an SSH key set up before using GSDeploy — see step 3 in Option B below.

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
Or download via browser

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
user@user: ~/Github/loputoo$ python3 -m venv gsdeploy-venv --system-site-packages
user@user: ~/Github/loputoo$ source gsdeploy-venv/bin/activate
user@user: ~/Github/loputoo$ pip install passlib
```

#### 5. Install Ansible collections

```bash
user@user: ~/Github/loputoo$ ansible-galaxy collection install -r requirements.txt
```

#### 6. Run GSDeploy

```bash
user@user: ~/Github/loputoo$ source gsdeploy-venv/bin/activate
user@user: ~/Github/loputoo$ python3 -m gsdeploy.main
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

***Note**
Connecting to VM via SSH once before provisioning is **mandatory** since Ansible rejects connecting to untrusted targets.

Click the provision button on the VM row. This connects to your existing VM via
password-based SSH, creates the admin user, installs Docker, node_exporter, and cAdvisor,
then switches all future connections to use the admin user and your SSH key.

> **Tip:** If you plan to use monitoring, add and provision the monitoring VM **before** provisioning
> game server VMs. This way promtail (log shipping) is automatically configured on game server VMs
> during provisioning. If you provision game server VMs first, you can re-provision them afterwards
> to add promtail.

### 3. Deploy Monitoring (optional)

Click **Deploy Monitoring** on the monitoring VM row. This deploys Prometheus, Loki, and Grafana.
Re-run it any time you change monitoring configuration.

If a monitoring VM is configured before provisioning, promtail is automatically set up on game
server VMs to ship logs to Loki.

Accessible at:
- Grafana: `http://<monitoring-ip>:3000`
- Prometheus: `http://<monitoring-ip>:9090`
- Loki: `http://<monitoring-ip>:3100`

### 4. Deploy Game Servers

Use the **Deploy** tab to walk through a wizard — select a VM, choose a game,
configure settings, and deploy.

### 5. Manage Servers

The **Dashboard** shows all deployed servers. From there you can start/stop containers,
view live Docker logs, view the deployment config, or remove a server. Removing a server
stops and removes the Docker container on the VM but leaves the data directory intact at
`/opt/gameservers/<server-name>/`.

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
| Server Type | `VANILLA` | `VANILLA`, `FORGE`, `NEOFORGE`, `FABRIC`, `PAPER`, `SPIGOT`, `QUILT` |

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
| Max Players | `16` | Maximum concurrent players |

### Factorio

| Field | Default | Description |
|---|---|---|
| Version | `latest` | Server version |
| Game Port | `34197` | UDP port players connect to |
| Max Players | `0` | Maximum concurrent players (0 = unlimited) |

---

## Game Server Data

Stored on the VM at `/opt/gameservers/<server-name>/`:

**Minecraft**
```
data/          — server root
data/mods/     — mod files (Forge, Fabric)
data/plugins/  — plugin files (Paper, Spigot)
data/world/    — world save files
```

**Valheim**
```
config/    — server configuration
data/      — world saves (created by container on first start)
```

**Vintage Story**
```
data/          — world saves and server data
data/config/   — server configuration files
```

**Factorio**
```
data/          — saves and server data
data/config/   — server configuration files
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

> **Security warning:** Prometheus, Loki, and the exporter ports have no authentication and Grafana runs plain HTTP. See [Using VMs on a Different Network](#using-vms-on-a-different-network) for firewall recommendations.

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

---

## Tech Stack

| Component | Technology |
|---|---|
| GUI | Python, GTK4, libadwaita |
| Automation | Ansible |
| Game servers | Docker, Docker Compose |
| Monitoring | Prometheus, Grafana, Loki, Promtail, cAdvisor, Node Exporter |
| Database | SQLite |
| Container log shipping | Loki Docker logging plugin |
| File transfer | rsync over SSH |

---

## Repository Structure

```
/loputoo
├── gsdeploy/              # Python application source
│   ├── pages/             # UI pages (Dashboard, Deploy, VM Manager, etc.)
│   ├── ansible_runner.py  # Ansible playbook execution and inventory management
│   ├── database.py        # SQLite database and migrations
│   ├── application.py     # App entry point
│   └── window.py          # Main window and navigation
├── playbooks/             # Ansible playbooks (provision, deploy, monitoring)
├── roles/                 # Ansible roles (docker, gameserver, grafana, etc.)
├── group_vars/            # Shared Ansible variables and vault
├── packaging/             # .deb package build scripts and metadata
└── requirements.txt       # Ansible Galaxy collections
```

---

## Contributing

Contributions are welcome. To contribute:

1. Fork the repository and clone your fork
2. Create a feature branch: `git checkout -b feat/your-feature`
3. Make your changes and test them locally
4. Use clear commit messages:
   - `feat:` — new feature
   - `fix:` — bug fix
   - `docs:` — documentation update
   - `refactor:` — code restructuring
5. Open a Pull Request with a description of your changes

Please keep PRs focused — one feature or fix per PR.

---

## License

This project is licensed under the [GNU General Public License v3.0](LICENSE).
