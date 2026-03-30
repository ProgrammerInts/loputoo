import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

import gsdeploy.database as db
import gsdeploy.ansible_runner as runner


GAME_ICONS = {
    "minecraft": "applications-games-symbolic",
    "valheim":   "applications-games-symbolic",
}


class DashboardPage(Gtk.ScrolledWindow):
    def __init__(self):
        super().__init__()
        self.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self._content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self._content.set_margin_top(24)
        self._content.set_margin_bottom(24)
        self._content.set_margin_start(24)
        self._content.set_margin_end(24)
        self.set_child(self._content)

        self.connect("map", lambda _: self._refresh())
        self._refresh()

    def _refresh(self):
        while self._content.get_first_child():
            self._content.remove(self._content.get_first_child())

        vms = db.get_vms()

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

                logs_btn = Gtk.Button(icon_name="utilities-terminal-symbolic")
                logs_btn.set_css_classes(["flat"])
                logs_btn.set_valign(Gtk.Align.CENTER)
                logs_btn.set_tooltip_text("View logs")
                logs_btn.connect("clicked", self._on_view_logs, dict(srv), dict(vm))
                row.add_suffix(logs_btn)

                remove_btn = Gtk.Button(icon_name="user-trash-symbolic")
                remove_btn.set_css_classes(["flat", "destructive-action"])
                remove_btn.set_valign(Gtk.Align.CENTER)
                remove_btn.set_tooltip_text("Remove server")
                remove_btn.connect("clicked", self._on_remove, dict(srv))
                row.add_suffix(remove_btn)

                group.add(row)

            self._content.append(group)

        if not any_servers:
            status = Adw.StatusPage()
            status.set_icon_name("applications-games-symbolic")
            status.set_title("No game servers deployed")
            status.set_description("Use Deploy Server to set up your first game server.")
            status.set_vexpand(True)
            self._content.append(status)

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

    # ── Remove ────────────────────────────────────────────────────────────────

    def _on_remove(self, _btn, srv):
        dialog = Adw.AlertDialog(
            heading=f"Remove \"{srv['name']}\"?",
            body="This removes the server from GSDeploy. "
                 "The Docker container will keep running on the VM — "
                 "stop it manually if needed.",
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("remove", "Remove")
        dialog.set_response_appearance("remove", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")
        dialog.connect("response", self._on_remove_confirmed, srv["id"])
        dialog.present(self)

    def _on_remove_confirmed(self, _dialog, response, server_id):
        if response == "remove":
            db.remove_server(server_id)
            self._refresh()
