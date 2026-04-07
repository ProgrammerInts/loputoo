import gi
import os
import json
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

import gsdeploy.database as db
import gsdeploy.ansible_runner as runner


GAME_ICONS = {
    "minecraft":    "applications-games-symbolic",
    "valheim":      "applications-games-symbolic",
    "vintagestory": "applications-games-symbolic",
    "factorio":     "applications-games-symbolic",
}


class DashboardPage(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)

        self._toast_overlay = Adw.ToastOverlay()

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)

        self._content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self._content.set_margin_top(24)
        self._content.set_margin_bottom(24)
        self._content.set_margin_start(24)
        self._content.set_margin_end(24)
        scroll.set_child(self._content)

        self._toast_overlay.set_child(scroll)
        self.append(self._toast_overlay)

        self.connect("map", lambda _: self._refresh())
        self._refresh()

    def _show_toast(self, message):
        toast = Adw.Toast(title=message)
        toast.set_timeout(5)
        toast.set_button_label("Copy")
        toast.connect("button-clicked", lambda t: self.get_clipboard().set(message))
        self._toast_overlay.add_toast(toast)

    def _refresh(self):
        while self._content.get_first_child():
            self._content.remove(self._content.get_first_child())

        vms = db.get_vms_by_type("game")

        if not vms:
            status = Adw.StatusPage()
            status.set_icon_name("org.gnome.SystemMonitor-symbolic")
            status.set_title("No VMs yet")
            status.set_description("Add a VM in Virtual Machines to get started.")
            status.set_vexpand(True)
            self._content.append(status)
            return

        any_servers = False

        for vm in vms:
            servers = db.get_servers(vm["id"])
            if not servers:
                continue

            any_servers = True
            group = Adw.PreferencesGroup(
                title=vm["name"],
                description=f"{vm['ssh_user']}@{vm['ip']}",
            )
            public_ip_btn = Gtk.Button(icon_name="network-transmit-receive-symbolic")
            public_ip_btn.set_css_classes(["flat"])
            public_ip_btn.set_tooltip_text("Get public IP")
            public_ip_btn.connect("clicked", self._on_get_public_ip, dict(vm), public_ip_btn)
            group.set_header_suffix(public_ip_btn)

            for srv in servers:
                icon = GAME_ICONS.get(srv["game_type"], "applications-games-symbolic")

                version = srv["version"]
                subtitle_parts = [srv["game_type"].capitalize()]
                if version:
                    subtitle_parts.append(version)
                subtitle_parts.append(f"port {srv['port']}")

                row = Adw.ActionRow(
                    title=srv["name"],
                    subtitle="  ·  ".join(subtitle_parts),
                )
                row.add_prefix(Gtk.Image.new_from_icon_name(icon))

                # Play / stop buttons (mutually visible based on container status)
                play_btn = Gtk.Button(icon_name="media-playback-start-symbolic")
                play_btn.set_css_classes(["flat"])
                play_btn.set_valign(Gtk.Align.CENTER)
                play_btn.set_tooltip_text("Start server")
                play_btn.set_sensitive(False)

                stop_btn = Gtk.Button(icon_name="media-playback-stop-symbolic")
                stop_btn.set_css_classes(["flat"])
                stop_btn.set_valign(Gtk.Align.CENTER)
                stop_btn.set_tooltip_text("Stop server")
                stop_btn.set_sensitive(False)

                restart_btn = Gtk.Button(icon_name="view-refresh-symbolic")
                restart_btn.set_css_classes(["flat"])
                restart_btn.set_valign(Gtk.Align.CENTER)
                restart_btn.set_tooltip_text("Restart server")
                restart_btn.set_sensitive(False)

                play_btn.connect("clicked", self._on_start, dict(srv), dict(vm), play_btn, stop_btn, restart_btn)
                stop_btn.connect("clicked", self._on_stop, dict(srv), dict(vm), play_btn, stop_btn, restart_btn)
                restart_btn.connect("clicked", self._on_restart, dict(srv), dict(vm), play_btn, stop_btn, restart_btn)

                row.add_suffix(play_btn)
                row.add_suffix(stop_btn)
                row.add_suffix(restart_btn)

                logs_btn = Gtk.Button(icon_name="utilities-terminal-symbolic")
                logs_btn.set_css_classes(["flat"])
                logs_btn.set_valign(Gtk.Align.CENTER)
                logs_btn.set_tooltip_text("View logs")
                logs_btn.connect("clicked", self._on_view_logs, dict(srv), dict(vm))
                row.add_suffix(logs_btn)

                files_btn = Gtk.Button(icon_name="folder-open-symbolic")
                files_btn.set_css_classes(["flat"])
                files_btn.set_valign(Gtk.Align.CENTER)
                files_btn.set_tooltip_text("Open server files in terminal")
                files_btn.connect("clicked", self._on_open_files, dict(srv), dict(vm))
                row.add_suffix(files_btn)

                if srv["game_type"] in ("minecraft", "vintagestory"):
                    console_btn = Gtk.Button(icon_name="input-keyboard-symbolic")
                    console_btn.set_css_classes(["flat"])
                    console_btn.set_valign(Gtk.Align.CENTER)
                    console_btn.set_tooltip_text("Open server console")
                    console_btn.connect("clicked", self._on_open_console, dict(srv), dict(vm))
                    row.add_suffix(console_btn)

                info_btn = Gtk.Button(icon_name="dialog-information-symbolic")
                info_btn.set_css_classes(["flat"])
                info_btn.set_valign(Gtk.Align.CENTER)
                info_btn.set_tooltip_text("Deployment configuration")
                info_btn.connect("clicked", self._on_show_config, dict(srv))
                row.add_suffix(info_btn)

                remove_btn = Gtk.Button(icon_name="user-trash-symbolic")
                remove_btn.set_css_classes(["flat", "destructive-action"])
                remove_btn.set_valign(Gtk.Align.CENTER)
                remove_btn.set_tooltip_text("Remove server")
                remove_btn.connect("clicked", self._on_remove, dict(srv), dict(vm))
                row.add_suffix(remove_btn)

                group.add(row)

                # Fetch status asynchronously and update buttons
                self._fetch_status(dict(vm), dict(srv), play_btn, stop_btn, restart_btn)

            self._content.append(group)

        if not any_servers:
            status = Adw.StatusPage()
            status.set_icon_name("applications-games-symbolic")
            status.set_title("No game servers deployed")
            status.set_description("Use Deploy Server to set up your first game server.")
            status.set_vexpand(True)
            self._content.append(status)

    # ── Start / Stop ─────────────────────────────────────────────────────────

    def _fetch_status(self, vm, srv, play_btn, stop_btn, restart_btn):
        def on_status(status):
            running = status == "running"
            play_btn.set_visible(not running)
            stop_btn.set_visible(running)
            play_btn.set_sensitive(True)
            stop_btn.set_sensitive(True)
            restart_btn.set_sensitive(running)

        runner.get_container_status(
            ip=vm["ip"],
            ssh_user=vm["ssh_user"],
            ssh_key=vm["ssh_key"],
            admin_password=vm["admin_password"],
            container=srv["name"],
            done_callback=on_status,
        )

    def _on_start(self, _btn, srv, vm, play_btn, stop_btn, restart_btn):
        play_btn.set_sensitive(False)
        stop_btn.set_sensitive(False)
        restart_btn.set_sensitive(False)

        def on_done(ok, error=None):
            if ok:
                self._show_toast(f"{srv['name']} started successfully")
            else:
                self._show_toast(f"Failed to start {srv['name']}: {error or 'unknown error'}")
            self._fetch_status(vm, srv, play_btn, stop_btn, restart_btn)

        runner.docker_action(
            ip=vm["ip"],
            ssh_user=vm["ssh_user"],
            ssh_key=vm["ssh_key"],
            admin_password=vm["admin_password"],
            container=srv["name"],
            action="start",
            done_callback=on_done,
        )

    def _on_stop(self, _btn, srv, vm, play_btn, stop_btn, restart_btn):
        play_btn.set_sensitive(False)
        stop_btn.set_sensitive(False)
        restart_btn.set_sensitive(False)

        def on_done(ok, error=None):
            if ok:
                self._show_toast(f"{srv['name']} stopped successfully")
            else:
                self._show_toast(f"Failed to stop {srv['name']}: {error or 'unknown error'}")
            self._fetch_status(vm, srv, play_btn, stop_btn, restart_btn)

        runner.docker_action(
            ip=vm["ip"],
            ssh_user=vm["ssh_user"],
            ssh_key=vm["ssh_key"],
            admin_password=vm["admin_password"],
            container=srv["name"],
            action="stop",
            done_callback=on_done,
        )

    def _on_restart(self, _btn, srv, vm, play_btn, stop_btn, restart_btn):
        play_btn.set_sensitive(False)
        stop_btn.set_sensitive(False)
        restart_btn.set_sensitive(False)

        def on_done(ok, error=None):
            if ok:
                self._show_toast(f"{srv['name']} restarted successfully")
            else:
                self._show_toast(f"Failed to restart {srv['name']}: {error or 'unknown error'}")
            self._fetch_status(vm, srv, play_btn, stop_btn, restart_btn)

        runner.docker_action(
            ip=vm["ip"],
            ssh_user=vm["ssh_user"],
            ssh_key=vm["ssh_key"],
            admin_password=vm["admin_password"],
            container=srv["name"],
            action="restart",
            done_callback=on_done,
        )

    # ── Log viewer ────────────────────────────────────────────────────────────

    def _on_view_logs(self, _btn, srv, vm):
        dialog = Adw.Dialog()
        dialog.set_title(f"Logs — {srv['name']}")
        dialog.set_content_width(700)
        dialog.set_content_height(500)

        toolbar_view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        toolbar_view.add_top_bar(header)

        buf = Gtk.TextBuffer()
        text_view = Gtk.TextView(buffer=buf)
        text_view.set_editable(False)
        text_view.set_monospace(True)
        text_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        text_view.set_css_classes(["card"])

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.set_margin_top(12)
        scroll.set_margin_bottom(12)
        scroll.set_margin_start(12)
        scroll.set_margin_end(12)
        scroll.set_child(text_view)

        toolbar_view.set_content(scroll)
        dialog.set_child(toolbar_view)

        def append_log(text):
            end = buf.get_end_iter()
            buf.insert(end, text)
            adj = scroll.get_vadjustment()
            if adj.get_value() >= adj.get_upper() - adj.get_page_size() - 20:
                text_view.scroll_to_iter(buf.get_end_iter(), 0, False, 0, 0)

        def on_done(ok):
            if not ok:
                append_log("\n[connection lost]\n")

        cancel = runner.stream_docker_logs(
            ip=vm["ip"],
            ssh_user=vm["ssh_user"],
            ssh_key=vm["ssh_key"],
            admin_password=vm["admin_password"],
            container=srv["name"],
            log_callback=append_log,
            done_callback=on_done,
        )

        dialog.connect("closed", lambda _: cancel())
        dialog.present(self)

    # ── Public IP ─────────────────────────────────────────────────────────────

    def _on_get_public_ip(self, _btn, vm, btn):
        btn.set_sensitive(False)
        def on_done(public_ip):
            btn.set_sensitive(True)
            if public_ip:
                toast = Adw.Toast(title=f"Public IP: {public_ip}")
                toast.set_timeout(0)
                toast.set_button_label("Copy")
                toast.connect("button-clicked", lambda t: self.get_clipboard().set(public_ip))
                self._toast_overlay.add_toast(toast)
            else:
                self._show_toast("Could not retrieve public IP — check SSH access and that curl is installed.")
        runner.get_public_ip(
            ip=vm["ip"],
            ssh_user=vm["ssh_user"],
            ssh_key=vm["ssh_key"],
            done_callback=on_done,
        )

    # ── Terminal shortcuts ────────────────────────────────────────────────────

    def _on_open_files(self, _btn, srv, vm):
        import shlex
        key = os.path.expanduser(vm["ssh_key"])
        ssh_cmd = [
            "ssh", "-i", key, "-t",
            "-o", "StrictHostKeyChecking=no",
            f"{vm['ssh_user']}@{vm['ip']}",
            f"cd /opt/gameservers/{shlex.quote(srv['name'])} && bash",
        ]
        if not runner.open_terminal(ssh_cmd):
            self._show_toast("No supported terminal emulator found.")

    def _on_open_console(self, _btn, srv, vm):
        import shlex
        key = os.path.expanduser(vm["ssh_key"])
        if srv["game_type"] == "minecraft":
            remote_cmd = (
                f"echo {shlex.quote(vm['admin_password'])} | sudo -S true 2>/dev/null && "
                f"sudo docker exec -it {shlex.quote(srv['name'])} rcon-cli"
            )
        else:  # vintagestory — show recent log history then attach for live I/O
            remote_cmd = (
                f"echo {shlex.quote(vm['admin_password'])} | sudo -S true 2>/dev/null && "
                f"sudo docker logs --tail 100 {shlex.quote(srv['name'])} 2>&1; "
                f"exec sudo docker attach {shlex.quote(srv['name'])}"
            )
        ssh_cmd = [
            "ssh", "-i", key, "-t",
            "-o", "StrictHostKeyChecking=no",
            f"{vm['ssh_user']}@{vm['ip']}",
            remote_cmd,
        ]
        if not runner.open_terminal(ssh_cmd):
            self._show_toast("No supported terminal emulator found.")

    # ── Remove ────────────────────────────────────────────────────────────────

    def _on_show_config(self, _btn, srv):
        config = json.loads(srv.get("config") or "{}")

        dialog = Adw.Dialog(title=f"{srv['name']} — Deployment Config")
        dialog.set_content_width(380)

        toolbar_view = Adw.ToolbarView()
        toolbar_view.add_top_bar(Adw.HeaderBar())

        group = Adw.PreferencesGroup()
        group.set_margin_top(16)
        group.set_margin_bottom(16)
        group.set_margin_start(16)
        group.set_margin_end(16)

        def add_row(title, value):
            r = Adw.ActionRow(title=title)
            r.set_subtitle(str(value) if value else "—")
            group.add(r)

        add_row("Game", srv["game_type"].capitalize())
        add_row("Port", srv["port"])
        if srv.get("version"):
            add_row("Version", srv["version"])

        LABELS = {
            "minecraft_type":         "Server Type",
            "minecraft_java_version": "Java Version",
            "minecraft_memory":       "Memory",
            "minecraft_mode":         "Game Mode",
            "minecraft_difficulty":   "Difficulty",
            "minecraft_max_players":  "Max Players",
            "valheim_world_name":     "World Name",
            "vs_world_name":          "World Name",
            "vs_max_clients":         "Max Players",
            "factorio_save_name":     "Save Name",
            "factorio_description":   "Description",
            "factorio_max_players":   "Max Players",
        }
        for key, label in LABELS.items():
            if key in config and config[key]:
                add_row(label, config[key])

        toolbar_view.set_content(group)
        dialog.set_child(toolbar_view)
        dialog.present(self)

    def _on_remove(self, _btn, srv, vm):
        dialog = Adw.AlertDialog(
            heading=f"Remove \"{srv['name']}\"?",
            body="The Docker container will be stopped and removed.\n\n"
                 "Server data (world files, mods, plugins) will be kept on the VM "
                 "at /opt/gameservers/" + srv['name'] + "/\n\n"
                 "If the VM or container no longer exists, use \"Remove Entry Only\" "
                 "to remove it from GSDeploy without touching the VM.",
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("entry_only", "Remove Entry Only")
        dialog.add_response("remove", "Remove")
        dialog.set_response_appearance("entry_only", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_response_appearance("remove", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")
        dialog.connect("response", self._on_remove_confirmed, dict(srv), dict(vm))
        dialog.present(self)

    def _on_remove_confirmed(self, _dialog, response, srv, vm):
        if response == "entry_only":
            db.remove_server(srv["id"])
            self._refresh()
            return
        if response != "remove":
            return

        dialog = Adw.Dialog()
        dialog.set_title(f"Removing {srv['name']}…")
        dialog.set_content_width(600)
        dialog.set_content_height(400)

        toolbar_view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        toolbar_view.add_top_bar(header)

        buf = Gtk.TextBuffer()
        text_view = Gtk.TextView(buffer=buf)
        text_view.set_editable(False)
        text_view.set_monospace(True)
        text_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        text_view.set_css_classes(["card"])

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.set_margin_top(12)
        scroll.set_margin_bottom(12)
        scroll.set_margin_start(12)
        scroll.set_margin_end(12)
        scroll.set_child(text_view)

        toolbar_view.set_content(scroll)
        dialog.set_child(toolbar_view)
        dialog.present(self)

        def append_log(text):
            end = buf.get_end_iter()
            buf.insert(end, text)
            adj = scroll.get_vadjustment()
            if adj.get_value() >= adj.get_upper() - adj.get_page_size() - 20:
                text_view.scroll_to_iter(buf.get_end_iter(), 0, False, 0, 0)

        def on_done(ok):
            if ok:
                append_log("\n✓ Server removed successfully.\n")
                db.remove_server(srv["id"])
                self._refresh()
            else:
                append_log("\n✗ Removal failed. Check the log above.\n")

        runner.run_remove_gameserver(
            vm_name=vm["hostname"],
            server_name=srv["name"],
            become_pass=vm["admin_password"],
            log_callback=append_log,
            done_callback=on_done,
        )
