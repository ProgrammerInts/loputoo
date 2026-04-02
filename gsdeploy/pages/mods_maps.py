import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk, Gio

import gsdeploy.database as db
import gsdeploy.ansible_runner as runner


# Remote destination paths per game type and transfer type
DESTINATIONS = {
    "minecraft": {
        "Mods":    "data/mods",
        "Plugins": "data/plugins",
        "World":   "data/world",
    },
    "valheim": {
        "World":   "config/worlds_local",
    },
    "vintagestory": {
        "Mods":  "data/Mods",
        "World": "data/Saves",
    },
}


class ModsMapsPage(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        self._selected_server = None  # dict with server + vm info
        self._cancel_fn = None

        self._build_ui()
        self.connect("map", lambda _: self._refresh_servers())

    def _build_ui(self):
        # Toast overlay wraps everything
        self._toast_overlay = Adw.ToastOverlay()
        self._toast_overlay.set_vexpand(True)

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

    def _refresh_servers(self):
        while self._content.get_first_child():
            self._content.remove(self._content.get_first_child())

        servers = db.get_servers()
        if not servers:
            status = Adw.StatusPage()
            status.set_icon_name("folder-symbolic")
            status.set_title("No game servers deployed")
            status.set_description("Deploy a game server first, then come back to add mods or maps.")
            status.set_vexpand(True)
            self._content.append(status)
            return

        # Build flat list of (server, vm) for selection
        self._server_list = []
        for srv in servers:
            vm = db.get_vm(srv["vm_id"])
            if vm:
                self._server_list.append((dict(srv), dict(vm)))

        # Collapsible notes & warnings
        expander = Gtk.Expander(label="Notes & Warnings")
        expander.set_expanded(True)

        notes_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        notes_box.set_margin_top(8)

        def _make_banner(icon_name, markup):
            label = Gtk.Label()
            label.set_markup(markup)
            label.set_wrap(True)
            label.set_xalign(0)
            label.set_css_classes(["dim-label"])
            label.set_margin_top(10)
            label.set_margin_end(12)
            label.set_margin_bottom(10)

            icon = Gtk.Image.new_from_icon_name(icon_name)
            icon.set_valign(Gtk.Align.START)
            icon.set_margin_top(12)
            icon.set_margin_start(12)
            icon.set_margin_end(4)
            icon.set_margin_bottom(10)

            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            box.set_css_classes(["card"])
            box.append(icon)
            box.append(label)
            return box

        notes_box.append(_make_banner(
            "dialog-information-symbolic",
            "Files are transferred from your selected local folder to the server's target folder via rsync — "
            "the folder itself is not copied, only its contents are. "
            "Consolidate mods into a single local folder before deploying to avoid transferring unintended files. "
            "After transfer, <b>restart the server from the Dashboard</b> for changes to take effect."
        ))
        notes_box.append(_make_banner(
            "dialog-warning-symbolic",
            "If you are adding mods that affect world generation, you will need to <b>delete the existing world files</b> "
            "and let the server regenerate the world on next start for those changes to apply. "
            "Game servers may behave differently — make sure you know what you are doing and "
            "<b>always make backups before deleting anything</b>."
        ))

        expander.set_child(notes_box)
        self._content.append(expander)

        # Server selector
        selector_group = Adw.PreferencesGroup(title="Target Server")
        server_names = [f"{srv['name']}  ({vm['name']})" for srv, vm in self._server_list]
        self._server_combo = Adw.ComboRow(title="Game Server")
        string_list = Gtk.StringList()
        for name in server_names:
            string_list.append(name)
        self._server_combo.set_model(string_list)
        self._server_combo.connect("notify::selected", self._on_server_changed)
        selector_group.add(self._server_combo)
        self._content.append(selector_group)

        # Transfer sections placeholder
        self._transfers_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self._content.append(self._transfers_box)

        # Log area
        self._log_buffer = Gtk.TextBuffer()
        log_view = Gtk.TextView(buffer=self._log_buffer)
        log_view.set_editable(False)
        log_view.set_monospace(True)
        log_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        log_view.set_css_classes(["card"])
        log_view.set_visible(False)
        self._log_view = log_view

        self._log_scroll = Gtk.ScrolledWindow()
        self._log_scroll.set_min_content_height(160)
        self._log_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self._log_scroll.set_child(log_view)
        self._log_scroll.set_visible(False)
        self._content.append(self._log_scroll)

        # Trigger initial selection
        if self._server_list:
            self._selected_server = self._server_list[0]
            self._rebuild_transfers()

    def _on_server_changed(self, combo, _param):
        idx = combo.get_selected()
        if idx < len(self._server_list):
            self._selected_server = self._server_list[idx]
            self._rebuild_transfers()

    def _rebuild_transfers(self):
        while self._transfers_box.get_first_child():
            self._transfers_box.remove(self._transfers_box.get_first_child())

        if not self._selected_server:
            return

        srv, vm = self._selected_server
        game_type = srv["game_type"]
        dest_map = DESTINATIONS.get(game_type, {})

        group = Adw.PreferencesGroup(title="Transfer Files")

        for label, dest_subdir in dest_map.items():
            path_entry = Gtk.Entry()
            path_entry.set_placeholder_text("Local path…")
            path_entry.set_hexpand(True)

            browse_btn = Gtk.Button(icon_name="folder-open-symbolic")
            browse_btn.set_valign(Gtk.Align.CENTER)
            browse_btn.set_tooltip_text("Select folder")
            browse_btn.connect("clicked", self._browse, path_entry, label)

            deploy_btn = Gtk.Button(label=f"Deploy {label}")
            deploy_btn.set_css_classes(["suggested-action"])
            deploy_btn.set_valign(Gtk.Align.CENTER)
            deploy_btn.connect("clicked", self._deploy, path_entry, dest_subdir, deploy_btn)

            path_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            path_box.set_margin_top(8)
            path_box.set_margin_bottom(8)
            path_box.set_margin_start(12)
            path_box.set_margin_end(12)
            path_box.append(path_entry)
            path_box.append(browse_btn)
            path_box.append(deploy_btn)

            row = Adw.ActionRow(title=label)
            row.set_subtitle(f"/opt/gameservers/{srv['name']}/{dest_subdir}/")
            row.add_suffix(path_box)

            group.add(row)

        self._transfers_box.append(group)

    def _browse(self, _btn, path_entry, label):
        dialog = Gtk.FileDialog()
        dialog.set_title(f"Select {label} folder")
        dialog.select_folder(self.get_root(), None, self._on_folder_done, path_entry)

    def _on_folder_done(self, dialog, result, path_entry):
        try:
            file = dialog.select_folder_finish(result)
        except Exception:
            return
        if file:
            path_entry.set_text(file.get_path())

    def _deploy(self, _btn, path_entry, dest_subdir, deploy_btn):
        local_path = path_entry.get_text().strip()
        if not local_path:
            self._show_toast("Please select a local path first.")
            return

        if not self._selected_server:
            return

        srv, vm = self._selected_server
        remote_dest = f"/opt/gameservers/{srv['name']}/{dest_subdir}/"

        self._log_buffer.set_text("")
        self._log_scroll.set_visible(True)
        self._log_view.set_visible(True)
        deploy_btn.set_sensitive(False)

        def on_done(ok):
            deploy_btn.set_sensitive(True)
            self._cancel_fn = None
            if ok:
                self._show_toast(f"Files deployed to {dest_subdir} successfully.")
            else:
                self._show_toast(f"Transfer failed — check the log below.")

        self._cancel_fn = runner.transfer_files(
            local_path=local_path,
            ip=vm["ip"],
            ssh_user=vm["ssh_user"],
            ssh_key=vm["ssh_key"],
            remote_dest=remote_dest,
            log_callback=self._append_log,
            done_callback=on_done,
        )

    def _append_log(self, text):
        end = self._log_buffer.get_end_iter()
        self._log_buffer.insert(end, text)
        adj = self._log_scroll.get_vadjustment()
        if adj.get_value() >= adj.get_upper() - adj.get_page_size() - 20:
            self._log_view.scroll_to_iter(self._log_buffer.get_end_iter(), 0, False, 0, 0)

    def _show_toast(self, message):
        toast = Adw.Toast(title=message)
        toast.set_button_label("Copy")
        toast.connect("button-clicked", lambda t: self.get_clipboard().set(message))
        self._toast_overlay.add_toast(toast)
