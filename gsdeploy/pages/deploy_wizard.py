import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk, Gdk

import gsdeploy.database as db
import gsdeploy.ansible_runner as runner


GAMES = [
    ("Minecraft",     "minecraft",     "applications-games-symbolic"),
    ("Valheim",       "valheim",       "applications-games-symbolic"),
    ("Vintage Story", "vintagestory",  "applications-games-symbolic"),
    ("Factorio",      "factorio",      "applications-games-symbolic"),
]


class DeployWizardPage(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        self._selected_vm    = None
        self._selected_game  = None
        self._pending_deploy = None
        self._cancel_deploy  = None

        self._build_ui()
        self.connect("map", self._on_map)

    def _on_map(self, _):
        self._populate_vm_list()

    def _build_ui(self):
        self._step_names = ["vm", "game", "configure", "deploy"]

        self.stack = Adw.ViewStack()
        self.stack.set_vexpand(True)

        self.stack.add_titled_with_icon(
            self._build_step_vm(), "vm", "Virtual Machine", "computer-symbolic")
        self.stack.add_titled_with_icon(
            self._build_step_game(), "game", "Game", "applications-games-symbolic")
        self.stack.add_titled_with_icon(
            self._build_step_configure(), "configure", "Configure", "preferences-other-symbolic")
        self.stack.add_titled_with_icon(
            self._build_step_deploy(), "deploy", "Deploy", "system-run-symbolic")

        switcher = Adw.ViewSwitcherBar()
        switcher.set_stack(self.stack)
        switcher.set_reveal(True)

        nav = Gtk.Box(spacing=8)
        nav.set_halign(Gtk.Align.CENTER)
        nav.set_margin_top(4)
        nav.set_margin_bottom(12)

        self.back_btn = Gtk.Button(label="Back")
        self.back_btn.set_sensitive(False)
        self.back_btn.connect("clicked", self._go_back)

        self.next_btn = Gtk.Button(label="Next")
        self.next_btn.set_css_classes(["suggested-action"])
        self.next_btn.connect("clicked", self._go_next)

        self.interrupt_btn = Gtk.Button(label="Interrupt")
        self.interrupt_btn.set_css_classes(["destructive-action"])
        self.interrupt_btn.set_visible(False)
        self.interrupt_btn.connect("clicked", self._on_interrupt)

        nav.append(self.back_btn)
        nav.append(self.next_btn)
        nav.append(self.interrupt_btn)

        # Bottom bar — pinned via ToolbarView so it never scrolls away
        bottom = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        bottom.append(switcher)
        bottom.append(nav)

        # Redirect Up from the bottom bar back into the step content
        def _focus_step_content():
            page = self.stack.get_visible_child()
            if page:
                page.child_focus(Gtk.DirectionType.TAB_BACKWARD)

        bottom_key = Gtk.EventControllerKey()
        def _on_bottom_key(_ctrl, keyval, _keycode, _state):
            if keyval == Gdk.KEY_Up:
                _focus_step_content()
                return True
            return False
        bottom_key.connect("key-pressed", _on_bottom_key)
        bottom.add_controller(bottom_key)

        content_scroll = Gtk.ScrolledWindow()
        content_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        content_scroll.set_vexpand(True)
        content_scroll.set_child(self.stack)

        toolbar_view = Adw.ToolbarView()
        toolbar_view.set_content(content_scroll)
        toolbar_view.add_bottom_bar(bottom)
        toolbar_view.set_vexpand(True)

        self._content_scroll = content_scroll
        self.log_scroll = content_scroll
        self.append(toolbar_view)

        self.stack.connect("notify::visible-child", self._on_page_changed)
        self.connect("map", self._on_map_connect_focus)

    def _on_map_connect_focus(self, _):
        if getattr(self, "_focus_handler_connected", False):
            return
        root = self.get_root()
        if root:
            root.connect("notify::focus-widget", self._on_focus_changed)
            self._focus_handler_connected = True

    def _on_focus_changed(self, window, _param):
        focused = window.get_focus()
        if focused is None:
            return
        # Only act if the focused widget is inside our content scroll
        parent = focused
        while parent:
            if parent is self._content_scroll:
                break
            parent = parent.get_parent()
        else:
            return
        ok, bounds = focused.compute_bounds(self._content_scroll)
        if not ok:
            return
        adj = self._content_scroll.get_vadjustment()
        widget_center = bounds.get_y() + bounds.get_height() / 2
        page_size = adj.get_page_size()
        new_value = widget_center - page_size / 2
        new_value = max(adj.get_lower(), min(adj.get_upper() - page_size, new_value))
        adj.set_value(new_value)

    # ── Step 1: Select VM ────────────────────────────────────────────────────

    def _build_step_vm(self):
        self._vm_step_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self._vm_step_box.set_halign(Gtk.Align.CENTER)
        self._vm_step_box.set_size_request(520, -1)
        self._vm_step_box.set_margin_top(24)
        self._vm_step_box.set_margin_bottom(24)
        self._vm_step_box.set_margin_start(24)
        self._vm_step_box.set_margin_end(24)

        label = Gtk.Label(label="Select a Virtual Machine")
        label.set_css_classes(["title-2"])
        label.set_halign(Gtk.Align.START)
        self._vm_step_box.append(label)

        self._vm_group_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self._vm_step_box.append(self._vm_group_box)

        self._populate_vm_list()
        return self._vm_step_box

    def _populate_vm_list(self):
        child = self._vm_group_box.get_first_child()
        if child:
            self._vm_group_box.remove(child)

        group = Adw.PreferencesGroup()
        vms = db.get_vms_by_type("game")

        if not vms:
            row = Adw.ActionRow(title="No VMs found", subtitle="Add a VM in Virtual Machines first")
            group.add(row)
        else:
            first_radio = None
            for vm in vms:
                radio = Gtk.CheckButton()
                if first_radio is None:
                    first_radio = radio
                else:
                    radio.set_group(first_radio)

                row = Adw.ActionRow(title=vm["name"], subtitle=f"{vm['ssh_user']}@{vm['ip']}")
                row.add_prefix(radio)
                row.set_activatable_widget(radio)
                radio.connect("toggled", self._on_vm_selected, dict(vm))
                group.add(row)

            if first_radio:
                first_radio.set_active(True)

        self._vm_group_box.append(group)

    def _on_vm_selected(self, radio, vm):
        if radio.get_active():
            self._selected_vm = vm


    # ── Step 2: Choose game ──────────────────────────────────────────────────

    def _build_step_game(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        box.set_halign(Gtk.Align.CENTER)
        box.set_size_request(520, -1)
        box.set_margin_top(24)
        box.set_margin_bottom(24)
        box.set_margin_start(24)
        box.set_margin_end(24)

        label = Gtk.Label(label="Choose Game")
        label.set_css_classes(["title-2"])
        label.set_halign(Gtk.Align.START)
        box.append(label)

        group = Adw.PreferencesGroup()
        first_radio = None
        for display_name, game_id, icon in GAMES:
            radio = Gtk.CheckButton()
            if first_radio is None:
                first_radio = radio
                self._selected_game = game_id
            else:
                radio.set_group(first_radio)

            row = Adw.ActionRow(title=display_name)
            row.add_prefix(Gtk.Image.new_from_icon_name(icon))
            row.add_prefix(radio)
            row.set_activatable_widget(radio)
            radio.connect("toggled", self._on_game_selected, game_id)
            group.add(row)

        if first_radio:
            first_radio.set_active(True)

        box.append(group)
        return box

    def _on_game_selected(self, radio, game_id):
        if radio.get_active():
            self._selected_game = game_id
            if hasattr(self, "_configure_group_box"):
                self._rebuild_configure_step()

    # ── Step 3: Configure ────────────────────────────────────────────────────

    def _build_step_configure(self):
        self._configure_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self._configure_box.set_halign(Gtk.Align.CENTER)
        self._configure_box.set_size_request(520, -1)
        self._configure_box.set_margin_top(24)
        self._configure_box.set_margin_bottom(24)
        self._configure_box.set_margin_start(24)
        self._configure_box.set_margin_end(24)

        self._configure_title = Gtk.Label(label="Configure Server")
        self._configure_title.set_css_classes(["title-2"])
        self._configure_title.set_halign(Gtk.Align.START)
        self._configure_box.append(self._configure_title)

        note_label = Gtk.Label()
        note_label.set_markup(
            "Server Name is the Docker container name — must be <b>unique across all VMs</b>. "
            "Use only letters, numbers, and hyphens (e.g. <tt>mc-survival</tt>, <tt>factorio1</tt>)."
        )
        note_label.set_wrap(True)
        note_label.set_xalign(0)
        note_label.set_css_classes(["dim-label"])
        note_label.set_focusable(False)
        self._configure_box.append(note_label)

        self._configure_group_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self._configure_box.append(self._configure_group_box)

        self._rebuild_configure_step()
        return self._configure_box

    def _rebuild_configure_step(self):
        child = self._configure_group_box.get_first_child()
        if child:
            self._configure_group_box.remove(child)

        group = Adw.PreferencesGroup()

        # Common fields
        self._server_name_row = Adw.EntryRow(title="Server Name")
        self._port_row        = Adw.EntryRow(title="Port")
        group.add(self._server_name_row)
        group.add(self._port_row)

        if self._selected_game == "minecraft":
            self._port_row.set_text("25565")

            # Server type dropdown
            MC_TYPES = ["VANILLA", "FORGE", "NEOFORGE", "FABRIC", "PAPER", "SPIGOT", "QUILT"]
            self._mc_type_row = Adw.ComboRow(title="Server Type")
            type_model = Gtk.StringList()
            for t in MC_TYPES:
                type_model.append(t)
            self._mc_type_row.set_model(type_model)  # defaults to index 0 = VANILLA

            # Java version dropdown
            MC_JAVA = ["java21", "java17", "java8", "java25"]
            self._mc_java_row = Adw.ComboRow(title="Java Version")
            java_model = Gtk.StringList()
            for j in MC_JAVA:
                java_model.append(j + (" (LTS, recommended)" if j == "java21" else ""))
            self._mc_java_row.set_model(java_model)  # defaults to index 0 = java21

            self._mc_version_row   = Adw.EntryRow(title="Minecraft Version")
            self._mc_memory_row    = Adw.EntryRow(title="Memory")
            self._mc_mode_row      = Adw.EntryRow(title="Game Mode")
            self._mc_difficulty_row= Adw.EntryRow(title="Difficulty")
            self._mc_max_players_row = Adw.EntryRow(title="Max Players")
            self._mc_version_row.set_text("LATEST")
            self._mc_memory_row.set_text("2G")
            self._mc_mode_row.set_text("survival")
            self._mc_difficulty_row.set_text("normal")
            self._mc_max_players_row.set_text("20")
            self._mc_whitelist_row = Adw.SwitchRow(title="Enable Whitelist",
                                                    subtitle="Only whitelisted players can join")
            mods_note = Adw.ActionRow(title="Mods &amp; modpacks")
            mods_note.set_subtitle("Add mods after deployment via the Modifications tab")
            mods_note.set_icon_name("dialog-information-symbolic")
            for row in [self._mc_type_row, self._mc_java_row, self._mc_version_row, self._mc_memory_row,
                        self._mc_mode_row, self._mc_difficulty_row,
                        self._mc_max_players_row, self._mc_whitelist_row, mods_note]:
                group.add(row)

        elif self._selected_game == "valheim":
            self._port_row.set_text("2456")
            self._vh_world_row = Adw.EntryRow(title="World Name")
            self._vh_pass_row  = Adw.PasswordEntryRow(title="Server Password")
            self._vh_world_row.set_text("Dedicated")
            group.add(self._vh_world_row)
            group.add(self._vh_pass_row)

        elif self._selected_game == "vintagestory":
            self._port_row.set_text("42420")
            self._vs_version_row     = Adw.EntryRow(title="Version")
            self._vs_world_row       = Adw.EntryRow(title="World Name")
            self._vs_max_players_row = Adw.EntryRow(title="Max Players")
            self._vs_pass_row        = Adw.PasswordEntryRow(title="Server Password (optional)")
            self._vs_version_row.set_text("1.21.6")
            self._vs_world_row.set_text("Default")
            self._vs_max_players_row.set_text("16")
            for row in [self._vs_version_row, self._vs_world_row,
                        self._vs_max_players_row, self._vs_pass_row]:
                group.add(row)

        elif self._selected_game == "factorio":
            self._port_row.set_text("34197")
            self._fac_version_row     = Adw.EntryRow(title="Version")
            self._fac_save_row        = Adw.EntryRow(title="Save Name")
            self._fac_desc_row        = Adw.EntryRow(title="Description (optional)")
            self._fac_max_players_row = Adw.EntryRow(title="Max Players (0 = unlimited)")
            self._fac_pass_row        = Adw.PasswordEntryRow(title="Server Password (optional)")
            self._fac_version_row.set_text("stable")
            self._fac_max_players_row.set_text("0")
            for row in [self._fac_version_row, self._fac_save_row, self._fac_desc_row,
                        self._fac_max_players_row, self._fac_pass_row]:
                group.add(row)

        self._configure_group_box.append(group)

    # ── Step 4: Deploy ───────────────────────────────────────────────────────

    def _build_step_deploy(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        box.set_hexpand(True)
        box.set_vexpand(True)
        box.set_margin_top(24)
        box.set_margin_bottom(24)
        box.set_margin_start(24)
        box.set_margin_end(24)

        label = Gtk.Label(label="Deployment Log")
        label.set_css_classes(["title-2"])
        label.set_halign(Gtk.Align.START)
        box.append(label)

        self.log_buffer = Gtk.TextBuffer()
        self.log_view = Gtk.TextView(buffer=self.log_buffer)
        self.log_view.set_editable(False)
        self.log_view.set_focusable(False)
        self.log_view.set_monospace(True)
        self.log_view.set_vexpand(True)
        self.log_view.set_css_classes(["card"])
        self.log_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)

        box.append(self.log_view)
        # assigned after _content_scroll is created in _build_ui
        self.log_scroll = None

        return box

    # ── Navigation ───────────────────────────────────────────────────────────

    def _warn_if_monitoring_not_deployed(self, on_proceed):
        if db.get_setting("monitoring_deployed") != "1":
            dialog = Adw.AlertDialog(
                heading="Monitoring not deployed",
                body="Monitoring has not been deployed yet. "
                     "Game server metrics won't be collected until you deploy monitoring "
                     "from the Virtual Machines page. Continue anyway?",
            )
            dialog.add_response("cancel", "Cancel")
            dialog.add_response("continue", "Continue Anyway")
            dialog.connect("response", lambda d, r: on_proceed() if r == "continue" else None)
            dialog.present(self)
        else:
            on_proceed()

    def _warn_if_not_provisioned(self, vm, on_proceed):
        if vm["ssh_user"] == vm["initial_user"]:
            dialog = Adw.AlertDialog(
                heading="VM may not be provisioned",
                body="This VM does not appear to have been provisioned yet. "
                     "Run Provision first to set up the admin user and required services. "
                     "Continue anyway?",
            )
            dialog.add_response("cancel", "Cancel")
            dialog.add_response("continue", "Continue Anyway")
            dialog.connect("response", lambda d, r: on_proceed() if r == "continue" else None)
            dialog.present(self)
        else:
            on_proceed()

    def _validate_configure(self):
        """Return an error string if configure step has invalid input, else None."""
        if self._selected_game == "valheim":
            password = self._vh_pass_row.get_text()
            world = self._vh_world_row.get_text().strip()
            if len(password) < 5:
                return "Valheim server password must be at least 5 characters."
            if password == world:
                return "Valheim server password cannot match the world name."
        return None

    def _show_validation_error(self, message):
        dialog = Adw.AlertDialog(heading="Invalid configuration", body=message)
        dialog.add_response("ok", "OK")
        dialog.present(self)

    def _current_idx(self):
        name = self.stack.get_visible_child_name()
        return self._step_names.index(name) if name in self._step_names else 0

    def _on_page_changed(self, _stack, _param):
        idx = self._current_idx()
        if idx == 0:
            self._populate_vm_list()
        self.back_btn.set_sensitive(idx > 0)
        if idx == len(self._step_names) - 1:
            self.next_btn.set_label("Deploy")
        else:
            self.next_btn.set_label("Next")

    def _find_listbox(self, widget):
        if isinstance(widget, Gtk.ListBox):
            return widget
        child = widget.get_first_child()
        while child:
            found = self._find_listbox(child)
            if found:
                return found
            child = child.get_next_sibling()
        return None

    def _go_next(self, _btn):
        idx = self._current_idx()
        total = len(self._step_names)

        if idx == total - 1:
            err = self._validate_configure()
            if err:
                self._show_validation_error(err)
                return
            self._warn_if_monitoring_not_deployed(
                lambda: self._warn_if_not_provisioned(self._selected_vm, self._start_deploy)
            )
            return

        if idx == 0 and self._selected_vm is None:
            return

        self.stack.set_visible_child_name(self._step_names[idx + 1])

    def _go_back(self, _btn):
        idx = self._current_idx()
        if idx > 0:
            self.stack.set_visible_child_name(self._step_names[idx - 1])

    # ── Deploy ───────────────────────────────────────────────────────────────

    def _on_interrupt(self, _btn):
        if self._cancel_deploy:
            self._cancel_deploy()
            self._cancel_deploy = None
        self.interrupt_btn.set_visible(False)
        self.interrupt_btn.set_sensitive(True)
        self._append_log("\n⚠ Interrupted by user.\n")
        p = self._pending_deploy
        if p:
            dialog = Adw.AlertDialog(
                heading="Clean up partial deployment?",
                body=f"The deployment of '{p['name']}' was interrupted. "
                     "Do you want to remove any partially deployed container? "
                     "Server data will be kept.",
            )
            dialog.add_response("keep", "Keep")
            dialog.add_response("cleanup", "Clean Up")
            dialog.set_response_appearance("cleanup", Adw.ResponseAppearance.DESTRUCTIVE)
            dialog.set_default_response("keep")
            dialog.set_close_response("keep")
            dialog.connect("response", self._on_interrupt_cleanup)
            dialog.present(self)
        else:
            self.next_btn.set_sensitive(True)
            self.back_btn.set_sensitive(True)
            self.next_btn.set_label("Deploy Again")

    def _on_interrupt_cleanup(self, _dialog, response):
        p = self._pending_deploy
        vm = self._selected_vm
        self.next_btn.set_sensitive(False)
        self.back_btn.set_sensitive(False)
        if response == "cleanup" and p and vm:
            self._append_log(f"\nCleaning up '{p['name']}'...\n")
            runner.run_remove_gameserver(
                vm_name=vm["hostname"],
                server_name=p["name"],
                become_pass=vm["admin_password"],
                log_callback=self._append_log,
                done_callback=lambda ok: self._on_cleanup_done(ok),
            )
        else:
            self.next_btn.set_sensitive(True)
            self.back_btn.set_sensitive(True)
            self.next_btn.set_label("Deploy Again")

    def _on_cleanup_done(self, ok):
        if ok:
            self._append_log("✓ Cleanup complete.\n")
        else:
            self._append_log("✗ Cleanup failed — check the VM manually.\n")
        self.next_btn.set_sensitive(True)
        self.back_btn.set_sensitive(True)
        self.next_btn.set_label("Deploy Again")

    def _start_deploy(self):
        self.log_buffer.set_text("")
        self.next_btn.set_sensitive(False)
        self.back_btn.set_sensitive(False)

        vm          = self._selected_vm
        game        = self._selected_game
        server_name = self._server_name_row.get_text().strip()
        port        = self._port_row.get_text().strip()
        become_pass = vm["admin_password"]

        extra_vars = {}
        if game == "minecraft":
            MC_TYPES = ["VANILLA", "FORGE", "NEOFORGE", "FABRIC", "PAPER", "SPIGOT", "QUILT"]
            MC_JAVA  = ["java21", "java17", "java8", "java25"]
            extra_vars["minecraft_type"]         = MC_TYPES[self._mc_type_row.get_selected()]
            extra_vars["minecraft_java_version"] = MC_JAVA[self._mc_java_row.get_selected()]
            extra_vars["minecraft_version"]    = self._mc_version_row.get_text().strip()
            extra_vars["minecraft_memory"]     = self._mc_memory_row.get_text().strip()
            extra_vars["minecraft_mode"]       = self._mc_mode_row.get_text().strip()
            extra_vars["minecraft_difficulty"] = self._mc_difficulty_row.get_text().strip()
            extra_vars["minecraft_max_players"]= self._mc_max_players_row.get_text().strip()
            extra_vars["minecraft_whitelist"]  = "true" if self._mc_whitelist_row.get_active() else "false"
        elif game == "valheim":
            extra_vars["valheim_world_name"]   = self._vh_world_row.get_text().strip()
            extra_vars["valheim_server_pass"]  = self._vh_pass_row.get_text()
        elif game == "vintagestory":
            extra_vars["vs_version"]           = self._vs_version_row.get_text().strip()
            extra_vars["vs_world_name"]        = self._vs_world_row.get_text().strip()
            extra_vars["vs_max_clients"]       = self._vs_max_players_row.get_text().strip()
            extra_vars["vs_password"]          = self._vs_pass_row.get_text()
        elif game == "factorio":
            extra_vars["factorio_version"]     = self._fac_version_row.get_text().strip()
            extra_vars["factorio_save_name"]   = self._fac_save_row.get_text().strip() or server_name
            extra_vars["factorio_description"] = self._fac_desc_row.get_text().strip()
            extra_vars["factorio_max_players"] = self._fac_max_players_row.get_text().strip()
            extra_vars["factorio_password"]    = self._fac_pass_row.get_text()

        version = ""
        if game == "minecraft":
            version = self._mc_version_row.get_text().strip()
        elif game == "vintagestory":
            version = self._vs_version_row.get_text().strip()
        elif game == "factorio":
            version = self._fac_version_row.get_text().strip()

        self._pending_deploy = {"vm_id": vm["id"], "name": server_name,
                                "game_type": game, "port": port, "version": version,
                                "config": extra_vars}

        self._append_log(f"Deploying {game} server '{server_name}' on {vm['name']}...\n\n")
        self.interrupt_btn.set_visible(True)

        self._cancel_deploy = runner.run_deploy_gameserver(
            vm_name=vm["hostname"],
            game_type=game,
            server_name=server_name,
            port=port,
            admin_username=vm["admin_username"],
            extra_vars=extra_vars,
            become_pass=become_pass,
            log_callback=self._append_log,
            done_callback=self._on_deploy_done,
        )

    def _on_deploy_done(self, success):
        self._cancel_deploy = None
        self.interrupt_btn.set_visible(False)
        if success:
            self._append_log("\n✓ Deployment completed successfully!\n")
            p = self._pending_deploy
            try:
                db.add_server(p["vm_id"], p["name"], p["game_type"], int(p["port"]), p.get("version", ""), p.get("config"))
            except Exception:
                pass
        else:
            self._append_log("\n✗ Deployment failed. Check the log above.\n")
        self.next_btn.set_sensitive(True)
        self.back_btn.set_sensitive(True)
        self.next_btn.set_label("Deploy Again")

    def _append_log(self, text):
        end = self.log_buffer.get_end_iter()
        self.log_buffer.insert(end, text)
        adj = self.log_scroll.get_vadjustment()
        if adj.get_value() >= adj.get_upper() - adj.get_page_size() - 20:
            end = self.log_buffer.get_end_iter()
            self.log_view.scroll_to_iter(end, 0, False, 0, 0)
