import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk


STEPS = [
    (
        "1. Add a Virtual Machine",
        "computer-symbolic",
        "Go to Virtual Machines and add an entry for each VM you want to use.\n\n"
        "You will need:\n"
        "• The VM's IP address — a static IP is strongly recommended, "
        "as a changing IP will break SSH connections and game server reachability\n"
        "• An existing SSH user on the VM (e.g. ubuntu)\n"
        "• A chosen admin username and password that GSDeploy will create\n"
        "• Your SSH key path (default: ~/.ssh/id_ed25519)",
    ),
    (
        "2. Provision the VM",
        "system-run-symbolic",
        "Click the provision button on the VM row. This connects to your existing VM, "
        "creates the admin user, installs Docker and required services, then switches "
        "all future connections to use the admin user and your SSH key.\n\n"
        "Provisioning only needs to be done once per VM.",
    ),
    (
        "3. Deploy Monitoring (Optional)",
        "utilities-system-monitor-symbolic",
        "If you have a dedicated monitoring VM, click Deploy Monitoring on it. "
        "This installs Prometheus, Grafana, and Loki for metrics and log collection.\n\n"
        "Monitoring only needs to be deployed once. New game servers register "
        "themselves automatically when deployed.",
    ),
    (
        "4. Deploy a Game Server",
        "applications-games-symbolic",
        "Go to Deploy Server and follow the wizard to select a VM, choose a game, "
        "configure settings, and deploy.\n\n"
        "Deployed servers appear on the Dashboard where you can start, stop, "
        "view logs, or remove them.",
    ),
]

MODIFICATIONS_STEPS = [
    (
        "How file transfer works",
        "folder-symbolic",
        "The Modifications tab transfers files from a local folder on your machine to the game server "
        "using rsync over SSH.\n\n"
        "Only the contents of your selected folder are copied — the folder itself is not. "
        "For example, if you select a folder containing mod1.jar and mod2.jar, those two files "
        "will be placed directly into the server's mods directory.\n\n"
        "Consolidate all mods you want to deploy into a single local folder before transferring.",
    ),
    (
        "After transferring files",
        "view-refresh-symbolic",
        "Changes do not take effect until the server is restarted. "
        "After a successful transfer, go to the Dashboard and use the Restart button on the server.\n\n"
        "Transferred files are additive — existing files on the server are not deleted. "
        "To remove a mod, connect via the Files button on the Dashboard and delete it manually.",
    ),
    (
        "World-generation mods",
        "dialog-warning-symbolic",
        "Mods that change world generation (new biomes, dimensions, structures) only affect "
        "chunks that have not yet been generated.\n\n"
        "If the world already exists, previously generated chunks will not change. "
        "To get a fully modded world you will need to delete the existing world files and "
        "let the server regenerate the world on next start.\n\n"
        "Always make a backup before deleting world files. Game servers may handle this differently — "
        "make sure you know what you are doing before proceeding.",
    ),
    (
        "Destination folders by game",
        "preferences-system-symbolic",
        "Each game type maps to different server directories:\n\n"
        "Minecraft\n"
        "• Mods → data/mods (Forge, Fabric, NeoForge, Quilt)\n"
        "• Plugins → data/plugins (Paper, Spigot)\n"
        "• World → data/world\n\n"
        "Vintage Story\n"
        "• Mods → data/Mods\n"
        "• World → data/Saves\n\n"
        "Valheim\n"
        "• World → config/worlds_local",
    ),
]

NETWORK_NOTE = (
    "Network Access",
    "network-transmit-receive-symbolic",
    "By default, game servers are only reachable within your local network or VPN.\n\n"
    "To allow players outside your network to connect:\n"
    "• Forward the game server port on your router to the VM's local IP address\n"
    "• Share your public IP address (or a domain name) with players\n\n"
    "Minecraft default port: 25565 (TCP)\n"
    "Valheim default ports: 2456–2457 (UDP)\n\n"
    "If you use a VPN (e.g. Tailscale, WireGuard), port forwarding is not needed — "
    "players connect through the VPN address instead.",
)


class GuidePage(Gtk.ScrolledWindow):
    def __init__(self):
        super().__init__()
        self.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        content.set_margin_top(24)
        content.set_margin_bottom(24)
        content.set_margin_start(24)
        content.set_margin_end(24)
        self.set_child(content)

        # Intro
        intro = Gtk.Label(
            label="GSDeploy lets you deploy and manage self-hosted game servers "
                  "on your own virtual machines using Ansible and Docker."
        )
        intro.set_wrap(True)
        intro.set_xalign(0)
        intro.set_css_classes(["dim-label"])
        content.append(intro)

        # Setup steps
        steps_group = Adw.PreferencesGroup(title="Getting Started")
        for title, icon, body in STEPS:
            row = Adw.ExpanderRow(title=title)
            row.add_prefix(Gtk.Image.new_from_icon_name(icon))

            label = Gtk.Label(label=body)
            label.set_wrap(True)
            label.set_xalign(0)
            label.set_margin_top(8)
            label.set_margin_bottom(8)
            label.set_margin_start(8)
            label.set_margin_end(8)
            row.add_row(label)

            steps_group.add(row)
        content.append(steps_group)

        # Modifications section
        mods_group = Adw.PreferencesGroup(title="Modifications")
        for title, icon, body in MODIFICATIONS_STEPS:
            row = Adw.ExpanderRow(title=title)
            row.add_prefix(Gtk.Image.new_from_icon_name(icon))

            label = Gtk.Label(label=body)
            label.set_wrap(True)
            label.set_xalign(0)
            label.set_margin_top(8)
            label.set_margin_bottom(8)
            label.set_margin_start(8)
            label.set_margin_end(8)
            row.add_row(label)

            mods_group.add(row)
        content.append(mods_group)

        # Network note
        net_title, net_icon, net_body = NETWORK_NOTE
        net_group = Adw.PreferencesGroup(title="Network Access")
        net_row = Adw.ExpanderRow(title=net_title)
        net_row.add_prefix(Gtk.Image.new_from_icon_name(net_icon))

        net_label = Gtk.Label(label=net_body)
        net_label.set_wrap(True)
        net_label.set_xalign(0)
        net_label.set_margin_top(8)
        net_label.set_margin_bottom(8)
        net_label.set_margin_start(8)
        net_label.set_margin_end(8)
        net_row.add_row(net_label)

        net_group.add(net_row)
        content.append(net_group)
