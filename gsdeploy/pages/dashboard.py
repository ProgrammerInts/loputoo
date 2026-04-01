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

                play_btn.connect("clicked", self._on_start, dict(srv), dict(vm), play_btn, stop_btn)
                stop_btn.connect("clicked", self._on_stop, dict(srv), dict(vm), play_btn, stop_btn)

                row.add_suffix(play_btn)
                row.add_suffix(stop_btn)

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
                remove_btn.connect("clicked", self._on_remove, dict(srv), dict(vm))
                row.add_suffix(remove_btn)

                group.add(row)

                # Fetch status asynchronously and update buttons
                self._fetch_status(dict(vm), dict(srv), play_btn, stop_btn)

            self._content.append(group)

        if not any_servers:
            status = Adw.StatusPage()
            status.set_icon_name("applications-games-symbolic")
            status.set_title("No game servers deployed")
            status.set_description("Use Deploy Server to set up your first game server.")
            status.set_vexpand(True)
            self._content.append(status)

    # ── Start / Stop ─────────────────────────────────────────────────────────

    def _fetch_status(self, vm, srv, play_btn, stop_btn):
        def on_status(status):
            running = status == "running"
            play_btn.set_visible(not running)
            stop_btn.set_visible(running)
            play_btn.set_sensitive(True)
            stop_btn.set_sensitive(True)

        runner.get_container_status(
            ip=vm["ip"],
            ssh_user=vm["ssh_user"],
            ssh_key=vm["ssh_key"],
            admin_password=vm["admin_password"],
            container=srv["name"],
            done_callback=on_status,
        )

    def _on_start(self, _btn, srv, vm, play_btn, stop_btn):
        play_btn.set_sensitive(False)
        stop_btn.set_sensitive(False)

        def on_done(ok, error=None):
            if ok:
                self._show_toast(f"{srv['name']} started successfully")
            else:
                self._show_toast(f"Failed to start {srv['name']}: {error or 'unknown error'}")
            self._fetch_status(vm, srv, play_btn, stop_btn)

        runner.docker_action(
            ip=vm["ip"],
            ssh_user=vm["ssh_user"],
            ssh_key=vm["ssh_key"],
            admin_password=vm["admin_password"],
            container=srv["name"],
            action="start",
            done_callback=on_done,
        )

    def _on_stop(self, _btn, srv, vm, play_btn, stop_btn):
        play_btn.set_sensitive(False)
        stop_btn.set_sensitive(False)

        def on_done(ok, error=None):
            if ok:
                self._show_toast(f"{srv['name']} stopped successfully")
            else:
                self._show_toast(f"Failed to stop {srv['name']}: {error or 'unknown error'}")
            self._fetch_status(vm, srv, play_btn, stop_btn)

        runner.docker_action(
            ip=vm["ip"],
            ssh_user=vm["ssh_user"],
            ssh_key=vm["ssh_key"],
            admin_password=vm["admin_password"],
            container=srv["name"],
            action="stop",
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

    # ── Remove ────────────────────────────────────────────────────────────────

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
