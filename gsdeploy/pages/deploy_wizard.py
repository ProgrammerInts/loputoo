import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

import gsdeploy.database as db
import gsdeploy.ansible_runner as runner


GAMES = [
    ("Minecraft", "minecraft", "applications-games-symbolic"),
    ("Valheim",   "valheim",   "applications-games-symbolic"),
]


class DeployWizardPage(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        self._selected_vm    = None
        self._selected_game  = None
        self._pending_deploy = None
        self._cancel_deploy  = None

        self._build_ui()
        self.connect("map", lambda _: self._populate_vm_list())

    def _build_ui(self):
        # Carousel
        self.carousel = Adw.Carousel()
        self.carousel.set_allow_scroll_wheel(False)
        self.carousel.set_allow_mouse_drag(False)
        self.carousel.set_vexpand(True)

        self.carousel.append(self._build_step_vm())
        self.carousel.append(self._build_step_game())
        self.carousel.append(self._build_step_configure())
        self.carousel.append(self._build_step_deploy())

        dots = Adw.CarouselIndicatorDots()
        dots.set_carousel(self.carousel)
        dots.set_margin_top(8)

        # Navigation buttons
        nav = Gtk.Box(spacing=8)
        nav.set_halign(Gtk.Align.CENTER)
        nav.set_margin_top(8)
        nav.set_margin_bottom(16)

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

        self.append(dots)
        self.append(self.carousel)
        self.append(nav)

        self.carousel.connect("page-changed", self._on_page_changed)

    # ── Step 1: Select VM ────────────────────────────────────────────────────

    def _build_step_vm(self):
        self._vm_step_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self._vm_step_box.set_margin_top(24)
        self._vm_step_box.set_margin_bottom(8)
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
        box.set_margin_top(24)
        box.set_margin_bottom(8)
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
        self._configure_box.set_margin_top(24)
        self._configure_box.set_margin_bottom(8)
        self._configure_box.set_margin_start(24)
        self._configure_box.set_margin_end(24)

        self._configure_title = Gtk.Label(label="Configure Server")
        self._configure_title.set_css_classes(["title-2"])
        self._configure_title.set_halign(Gtk.Align.START)
        self._configure_box.append(self._configure_title)

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
            self._mc_version_row   = Adw.EntryRow(title="Version")
            self._mc_memory_row    = Adw.EntryRow(title="Memory")
            self._mc_mode_row      = Adw.EntryRow(title="Game Mode")
            self._mc_difficulty_row= Adw.EntryRow(title="Difficulty")
            self._mc_max_players_row = Adw.EntryRow(title="Max Players")
            self._mc_version_row.set_text("LATEST")
            self._mc_memory_row.set_text("2G")
            self._mc_mode_row.set_text("survival")
            self._mc_difficulty_row.set_text("normal")
            self._mc_max_players_row.set_text("20")
            for row in [self._mc_version_row, self._mc_memory_row,
                        self._mc_mode_row, self._mc_difficulty_row,
                        self._mc_max_players_row]:
                group.add(row)

        elif self._selected_game == "valheim":
            self._port_row.set_text("2456")
            self._vh_world_row = Adw.EntryRow(title="World Name")
            self._vh_pass_row  = Adw.PasswordEntryRow(title="Server Password")
            self._vh_world_row.set_text("Dedicated")
            group.add(self._vh_world_row)
            group.add(self._vh_pass_row)

        self._configure_group_box.append(group)

    # ── Step 4: Deploy ───────────────────────────────────────────────────────

    def _build_step_deploy(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        box.set_margin_top(24)
        box.set_margin_bottom(8)
        box.set_margin_start(24)
        box.set_margin_end(24)

        label = Gtk.Label(label="Deployment Log")
        label.set_css_classes(["title-2"])
        label.set_halign(Gtk.Align.START)
        box.append(label)

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

        self.log_buffer = Gtk.TextBuffer()
        self.log_view = Gtk.TextView(buffer=self.log_buffer)
        self.log_view.set_editable(False)
        self.log_view.set_monospace(True)
        self.log_view.set_css_classes(["card"])
        self.log_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)

        scroll.set_child(self.log_view)
        self.log_scroll = scroll
        box.append(scroll)

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

    def _on_page_changed(self, carousel, idx):
        if idx == 0:
            self._populate_vm_list()
        self.back_btn.set_sensitive(idx > 0)
        total = carousel.get_n_pages()
        if idx == total - 1:
            self.next_btn.set_label("Deploy")
            self.next_btn.set_css_classes(["suggested-action"])
        else:
            self.next_btn.set_label("Next")

    def _go_next(self, _btn):
        idx = int(self.carousel.get_position())
        total = self.carousel.get_n_pages()

        if idx == total - 1:
            err = self._validate_configure()
            if err:
                self._show_validation_error(err)
                return
            self._warn_if_monitoring_not_deployed(
                lambda: self._warn_if_not_provisioned(self._selected_vm, self._start_deploy)
            )
            return

        # Validate step 1
        if idx == 0 and self._selected_vm is None:
            return

        next_page = self.carousel.get_nth_page(idx + 1)
        self.carousel.scroll_to(next_page, True)

    def _go_back(self, _btn):
        idx = int(self.carousel.get_position())
        if idx > 0:
            prev_page = self.carousel.get_nth_page(idx - 1)
            self.carousel.scroll_to(prev_page, True)

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
            extra_vars["minecraft_version"]   = self._mc_version_row.get_text().strip()
            extra_vars["minecraft_memory"]     = self._mc_memory_row.get_text().strip()
            extra_vars["minecraft_mode"]       = self._mc_mode_row.get_text().strip()
            extra_vars["minecraft_difficulty"] = self._mc_difficulty_row.get_text().strip()
            extra_vars["minecraft_max_players"]= self._mc_max_players_row.get_text().strip()
        elif game == "valheim":
            extra_vars["valheim_world_name"]   = self._vh_world_row.get_text().strip()
            extra_vars["valheim_server_pass"]  = self._vh_pass_row.get_text()

        version = ""
        if game == "minecraft":
            version = self._mc_version_row.get_text().strip()

        self._pending_deploy = {"vm_id": vm["id"], "name": server_name,
                                "game_type": game, "port": port, "version": version}

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
                db.add_server(p["vm_id"], p["name"], p["game_type"], int(p["port"]), p.get("version", ""))
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
