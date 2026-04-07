import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

import gsdeploy.database as db
import gsdeploy.ansible_runner as runner


class VMManagerPage(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        self._toast_overlay = Adw.ToastOverlay()
        self._toast_overlay.set_vexpand(True)

        inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        inner.set_margin_top(24)
        inner.set_margin_bottom(24)
        inner.set_margin_start(24)
        inner.set_margin_end(24)
        self._toast_overlay.set_child(inner)
        self.append(self._toast_overlay)

        # Toolbar
        toolbar = Gtk.Box(spacing=8)
        toolbar.set_halign(Gtk.Align.END)
        toolbar.set_margin_bottom(12)
        add_btn = Gtk.Button(label="Add VM")
        add_btn.set_css_classes(["suggested-action", "pill"])
        add_btn.connect("clicked", self._show_add_dialog)
        toolbar.append(add_btn)
        inner.append(toolbar)

        # Container for groups (rebuilt on refresh)
        self.group_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        inner.append(self.group_box)

        # Empty state
        self.empty_label = Gtk.Label(label="No VMs added yet. Click \"Add VM\" to get started.")
        self.empty_label.set_css_classes(["dim-label"])
        self.empty_label.set_margin_top(24)
        inner.append(self.empty_label)

        self._refresh()

    def _refresh(self):
        while self.group_box.get_first_child():
            self.group_box.remove(self.group_box.get_first_child())

        vms = db.get_vms()
        self.empty_label.set_visible(len(vms) == 0)

        game_vms       = [v for v in vms if v["vm_type"] == "game"]
        monitoring_vms = [v for v in vms if v["vm_type"] == "monitoring"]

        if monitoring_vms:
            mon_group = Adw.PreferencesGroup(
                title="Monitoring VM",
                description="Hosts Prometheus, Loki and Grafana",
            )
            for vm in monitoring_vms:
                self._add_vm_row(mon_group, vm, is_monitoring=True)
            self.group_box.append(mon_group)

        if game_vms:
            game_group = Adw.PreferencesGroup(
                title="Game Server VMs",
                description="VMs available for game server deployment",
            )
            for vm in game_vms:
                self._add_vm_row(game_group, vm, is_monitoring=False)
            self.group_box.append(game_group)

    def _add_vm_row(self, group, vm, is_monitoring=False):
        icon = "utilities-system-monitor-symbolic" if is_monitoring else "computer-symbolic"
        row = Adw.ActionRow(title=vm["name"], subtitle=f"{vm['ssh_user']}@{vm['ip']}")
        row.add_prefix(Gtk.Image.new_from_icon_name(icon))

        check_btn = Gtk.Button(icon_name="network-transmit-receive-symbolic")
        check_btn.set_css_classes(["flat"])
        check_btn.set_valign(Gtk.Align.CENTER)
        check_btn.set_tooltip_text("Check connection")
        check_btn.connect("clicked", self._on_check_connection, dict(vm), check_btn)
        row.add_suffix(check_btn)

        provision_btn = Gtk.Button(icon_name="system-run-symbolic")
        provision_btn.set_css_classes(["flat"])
        provision_btn.set_valign(Gtk.Align.CENTER)
        provision_btn.set_tooltip_text("Provision VM")
        provision_btn.connect("clicked", self._show_provision_dialog, dict(vm))
        row.add_suffix(provision_btn)

        if is_monitoring:
            deploy_btn = Gtk.Button(label="Deploy Monitoring")
            deploy_btn.set_css_classes(["flat"])
            deploy_btn.set_valign(Gtk.Align.CENTER)
            deploy_btn.connect("clicked", lambda b, v=dict(vm): self._warn_if_not_provisioned(v, lambda: self._on_deploy_monitoring(b, v)))
            row.add_suffix(deploy_btn)

        edit_btn = Gtk.Button(icon_name="document-edit-symbolic")
        edit_btn.set_css_classes(["flat"])
        edit_btn.set_valign(Gtk.Align.CENTER)
        edit_btn.set_tooltip_text("Edit VM")
        edit_btn.connect("clicked", self._show_edit_dialog, dict(vm))
        row.add_suffix(edit_btn)

        remove_btn = Gtk.Button(icon_name="user-trash-symbolic")
        remove_btn.set_css_classes(["flat"])
        remove_btn.set_valign(Gtk.Align.CENTER)
        remove_btn.set_tooltip_text("Remove VM")
        remove_btn.connect("clicked", self._on_remove, vm["id"])
        row.add_suffix(remove_btn)

        group.add(row)

    def _show_toast(self, message):
        toast = Adw.Toast(title=message)
        toast.set_timeout(4)
        self._toast_overlay.add_toast(toast)

    def _on_check_connection(self, _btn, vm, btn):
        btn.set_sensitive(False)
        btn.set_icon_name("content-loading-symbolic")

        def on_done(ok):
            btn.set_sensitive(True)
            if ok:
                btn.set_icon_name("emblem-ok-symbolic")
                self._show_toast(f"{vm['name']} is reachable")
            else:
                btn.set_icon_name("dialog-error-symbolic")
                self._show_toast(f"{vm['name']} is not reachable — check IP and that the VM is online")

        runner.check_connection(
            ip=vm["ip"],
            ssh_user=vm["ssh_user"],
            ssh_key=vm["ssh_key"],
            done_callback=on_done,
        )

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

    def _on_deploy_monitoring(self, _btn, vm):
        dialog = Adw.Dialog(title="Deploy Monitoring")
        dialog.set_content_width(420)

        toolbar_view = Adw.ToolbarView()
        header_bar = Adw.HeaderBar()
        toolbar_view.add_top_bar(header_bar)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        group = Adw.PreferencesGroup()
        group.set_margin_top(16)
        group.set_margin_bottom(8)
        group.set_margin_start(16)
        group.set_margin_end(16)

        self._mon_log_buffer = Gtk.TextBuffer()
        self._mon_log_view = Gtk.TextView(buffer=self._mon_log_buffer)
        self._mon_log_view.set_editable(False)
        self._mon_log_view.set_monospace(True)
        self._mon_log_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)

        scroll = Gtk.ScrolledWindow()
        scroll.set_min_content_height(200)
        scroll.set_child(self._mon_log_view)
        scroll.set_margin_start(16)
        scroll.set_margin_end(16)
        scroll.set_visible(False)
        self._mon_scroll = scroll

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_box.set_halign(Gtk.Align.CENTER)
        btn_box.set_margin_top(8)
        btn_box.set_margin_bottom(16)

        deploy_btn = Gtk.Button(label="Deploy")
        deploy_btn.set_css_classes(["suggested-action", "pill"])

        interrupt_btn = Gtk.Button(label="Interrupt")
        interrupt_btn.set_css_classes(["destructive-action", "pill"])
        interrupt_btn.set_visible(False)

        mon_spinner = Gtk.Spinner()
        mon_spinner.set_margin_top(4)
        mon_spinner.set_margin_bottom(4)
        mon_spinner.set_visible(False)
        self._mon_spinner = mon_spinner

        deploy_btn.connect("clicked", self._run_monitoring_deploy, vm, dialog, deploy_btn, interrupt_btn)
        interrupt_btn.connect("clicked", self._interrupt_monitoring, interrupt_btn, deploy_btn)

        btn_box.append(mon_spinner)
        btn_box.append(deploy_btn)
        btn_box.append(interrupt_btn)

        content.append(scroll)
        content.append(btn_box)
        toolbar_view.set_content(content)
        dialog.set_child(toolbar_view)
        dialog.present(self)

    def _run_monitoring_deploy(self, _btn, vm, dialog, deploy_btn, interrupt_btn):
        self._mon_scroll.set_visible(True)
        deploy_btn.set_sensitive(False)
        interrupt_btn.set_visible(True)
        self._mon_spinner.set_visible(True)
        self._mon_spinner.start()

        def _on_mon_done(ok):
            self._mon_spinner.stop()
            self._mon_spinner.set_visible(False)
            deploy_btn.set_sensitive(True)
            interrupt_btn.set_visible(False)
            self._mon_cancel = None
            if ok:
                db.set_setting("monitoring_deployed", "1")

        self._mon_cancel = runner.run_deploy_monitoring(
            vm_name=vm["hostname"],
            become_pass=vm["admin_password"],
            log_callback=self._mon_log,
            done_callback=_on_mon_done,
        )

    def _interrupt_monitoring(self, _btn, interrupt_btn, deploy_btn):
        if getattr(self, "_mon_cancel", None):
            self._mon_cancel()
            self._mon_cancel = None
        interrupt_btn.set_visible(False)
        deploy_btn.set_sensitive(True)
        self._mon_spinner.stop()
        self._mon_spinner.set_visible(False)
        self._mon_log("\n⚠ Interrupted by user. Monitoring may be partially installed.\n")

    def _mon_log(self, text):
        end = self._mon_log_buffer.get_end_iter()
        self._mon_log_buffer.insert(end, text)
        adj = self._mon_scroll.get_vadjustment()
        if adj.get_value() >= adj.get_upper() - adj.get_page_size() - 20:
            end = self._mon_log_buffer.get_end_iter()
            self._mon_log_view.scroll_to_iter(end, 0, False, 0, 0)

    def _on_remove(self, btn, vm_id):
        dialog = Adw.AlertDialog(
            heading="Remove VM?",
            body="This will remove the VM from GSDeploy. The VM itself will not be affected.",
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("remove", "Remove")
        dialog.set_response_appearance("remove", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.connect("response", self._on_remove_confirmed, vm_id)
        dialog.present(self)

    def _on_remove_confirmed(self, dialog, response, vm_id):
        if response == "remove":
            vm = db.get_vm(vm_id)
            db.remove_vm(vm_id)
            if vm:
                try:
                    runner.remove_from_inventory(vm["hostname"])
                except Exception:
                    pass
            self._refresh()

    def _show_add_dialog(self, _btn):
        dialog = Adw.Dialog(title="Add Virtual Machine")
        dialog.set_content_width(420)

        toolbar_view = Adw.ToolbarView()
        toolbar_view.add_top_bar(Adw.HeaderBar())

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        group = Adw.PreferencesGroup()
        group.set_margin_top(16)
        group.set_margin_bottom(8)
        group.set_margin_start(16)
        group.set_margin_end(16)

        self._name_row        = Adw.EntryRow(title="Name")
        self._ip_row          = Adw.EntryRow(title="IP Address")
        self._user_row        = Adw.EntryRow(title="Initial SSH User")
        self._admin_user_row  = Adw.EntryRow(title="Admin Username")
        self._admin_user_row.set_text("admin")
        self._admin_pass_row  = Adw.PasswordEntryRow(title="Admin Password")
        self._key_row         = Adw.EntryRow(title="SSH Key Path")
        self._key_row.set_text("~/.ssh/id_ed25519")

        # VM type selector
        self._type_row = Adw.ComboRow(title="VM Type")
        type_model = Gtk.StringList.new(["Game Server", "Monitoring"])
        self._type_row.set_model(type_model)
        self._type_row.set_selected(0)

        for row in [self._name_row, self._ip_row, self._user_row,
                    self._admin_user_row, self._admin_pass_row, self._key_row]:
            group.add(row)
            row.connect("changed", lambda _: self._error_label.set_visible(False))
        group.add(self._type_row)

        self._error_label = Gtk.Label(label="")
        self._error_label.set_css_classes(["error"])
        self._error_label.set_margin_start(16)
        self._error_label.set_margin_end(16)
        self._error_label.set_visible(False)

        add_btn = Gtk.Button(label="Add VM")
        add_btn.set_css_classes(["suggested-action", "pill"])
        add_btn.set_margin_start(16)
        add_btn.set_margin_end(16)
        add_btn.set_margin_top(8)
        add_btn.set_margin_bottom(16)
        add_btn.connect("clicked", self._on_add_confirmed, dialog)

        content.append(group)
        content.append(self._error_label)
        content.append(add_btn)
        toolbar_view.set_content(content)
        dialog.set_child(toolbar_view)
        dialog.present(self)

    def _on_add_confirmed(self, _btn, dialog):
        name       = self._name_row.get_text().strip()
        ip         = self._ip_row.get_text().strip()
        user       = self._user_row.get_text().strip()
        admin_user = self._admin_user_row.get_text().strip()
        admin_pass = self._admin_pass_row.get_text()
        key        = self._key_row.get_text().strip()
        vm_type    = "monitoring" if self._type_row.get_selected() == 1 else "game"

        if not name or not ip or not user or not admin_user or not admin_pass:
            self._show_error("All fields are required.")
            return

        if db.slugify(name) in ("all", "ungrouped", "localhost") or \
           (vm_type == "game" and db.slugify(name) == "monitoring"):
            self._show_error(f"'{name}' is a reserved name, please choose a different name.")
            return

        if vm_type == "monitoring" and db.get_vms_by_type("monitoring"):
            self._show_error("A monitoring VM already exists. Only one monitoring VM is supported.")
            return

        try:
            db.add_vm(name, ip, user, admin_user, admin_pass, key, vm_type)
        except Exception as e:
            self._show_error(str(e))
            return

        try:
            hostname = db.slugify(name)
            runner.add_to_inventory(hostname, ip, user, key, vm_type)
        except Exception as e:
            self._show_error(f"VM added but inventory update failed: {e}")
            return

        dialog.close()
        self._refresh()

    def _show_provision_dialog(self, _btn, vm):
        dialog = Adw.Dialog(title=f"Provision {vm['name']}")
        dialog.set_content_width(420)

        toolbar_view = Adw.ToolbarView()
        toolbar_view.add_top_bar(Adw.HeaderBar())

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        group = Adw.PreferencesGroup()
        group.set_margin_top(16)
        group.set_margin_bottom(8)
        group.set_margin_start(16)
        group.set_margin_end(16)

        self._prov_become_row = Adw.PasswordEntryRow(title=f"Password for {vm['initial_user']}")
        group.add(self._prov_become_row)

        self._prov_log_buffer = Gtk.TextBuffer()
        self._prov_log_view = Gtk.TextView(buffer=self._prov_log_buffer)
        self._prov_log_view.set_editable(False)
        self._prov_log_view.set_monospace(True)
        self._prov_log_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)

        scroll = Gtk.ScrolledWindow()
        scroll.set_min_content_height(200)
        scroll.set_child(self._prov_log_view)
        scroll.set_margin_start(16)
        scroll.set_margin_end(16)
        scroll.set_visible(False)
        self._prov_scroll = scroll

        spinner = Gtk.Spinner()
        spinner.set_margin_top(4)
        spinner.set_margin_bottom(4)
        spinner.set_visible(False)
        self._prov_spinner = spinner

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_box.set_halign(Gtk.Align.CENTER)
        btn_box.set_margin_top(8)
        btn_box.set_margin_bottom(16)

        provision_btn = Gtk.Button(label="Provision")
        provision_btn.set_css_classes(["suggested-action", "pill"])

        interrupt_btn = Gtk.Button(label="Interrupt")
        interrupt_btn.set_css_classes(["destructive-action", "pill"])
        interrupt_btn.set_visible(False)

        provision_btn.connect("clicked", self._run_provision, vm, dialog, provision_btn, interrupt_btn)
        interrupt_btn.connect("clicked", self._interrupt_provision, interrupt_btn, provision_btn)

        btn_box.append(spinner)
        btn_box.append(provision_btn)
        btn_box.append(interrupt_btn)

        content.append(group)
        content.append(scroll)
        content.append(btn_box)
        toolbar_view.set_content(content)
        dialog.set_child(toolbar_view)
        dialog.present(self)

    def _run_provision(self, _btn, vm, dialog, provision_btn, interrupt_btn):
        become_pass = self._prov_become_row.get_text()
        self._prov_scroll.set_visible(True)
        provision_btn.set_sensitive(False)
        interrupt_btn.set_visible(True)
        self._prov_spinner.set_visible(True)
        self._prov_spinner.start()

        def on_done(success):
            self._prov_spinner.stop()
            self._prov_spinner.set_visible(False)
            provision_btn.set_sensitive(True)
            interrupt_btn.set_visible(False)
            self._prov_cancel = None
            if success:
                db.set_vm_ssh_user(vm["id"], vm["admin_username"])
                runner.add_to_inventory(
                    vm["hostname"], vm["ip"], vm["admin_username"], vm["ssh_key"], vm["vm_type"]
                )
                self._refresh()

        self._prov_cancel = runner.run_provision_vm(
            hostname=vm["hostname"],
            ip=vm["ip"],
            initial_user=vm["initial_user"],
            initial_ssh_pass=become_pass,
            admin_username=vm["admin_username"],
            admin_password=vm["admin_password"],
            deployer_ssh_key=vm["ssh_key"],
            log_callback=self._prov_log,
            done_callback=on_done,
        )

    def _interrupt_provision(self, _btn, interrupt_btn, provision_btn):
        if getattr(self, "_prov_cancel", None):
            self._prov_cancel()
            self._prov_cancel = None
        interrupt_btn.set_visible(False)
        self._prov_spinner.stop()
        self._prov_spinner.set_visible(False)
        provision_btn.set_sensitive(True)
        self._prov_log("\n⚠ Interrupted by user. VM may be partially provisioned — re-run provisioning to fix.\n")

    def _prov_log(self, text):
        end = self._prov_log_buffer.get_end_iter()
        self._prov_log_buffer.insert(end, text)
        adj = self._prov_scroll.get_vadjustment()
        if adj.get_value() >= adj.get_upper() - adj.get_page_size() - 20:
            end = self._prov_log_buffer.get_end_iter()
            self._prov_log_view.scroll_to_iter(end, 0, False, 0, 0)

    def _show_edit_dialog(self, _btn, vm):
        dialog = Adw.Dialog(title="Edit Virtual Machine")
        dialog.set_content_width(420)

        toolbar_view = Adw.ToolbarView()
        toolbar_view.add_top_bar(Adw.HeaderBar())

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        group = Adw.PreferencesGroup()
        group.set_margin_top(16)
        group.set_margin_bottom(8)
        group.set_margin_start(16)
        group.set_margin_end(16)

        self._edit_name_row       = Adw.EntryRow(title="Name")
        self._edit_name_row.set_text(vm["name"])
        self._edit_ip_row         = Adw.EntryRow(title="IP Address")
        self._edit_ip_row.set_text(vm["ip"])
        self._edit_user_row       = Adw.EntryRow(title="Initial SSH User")
        self._edit_user_row.set_text(vm["initial_user"])
        self._edit_admin_user_row = Adw.EntryRow(title="Admin Username")
        self._edit_admin_user_row.set_text(vm["admin_username"])
        self._edit_admin_pass_row = Adw.PasswordEntryRow(title="Admin Password")
        self._edit_admin_pass_row.set_text(vm["admin_password"])
        self._edit_key_row        = Adw.EntryRow(title="SSH Key Path")
        self._edit_key_row.set_text(vm["ssh_key"])

        self._edit_type_row = Adw.ComboRow(title="VM Type")
        type_model = Gtk.StringList.new(["Game Server", "Monitoring"])
        self._edit_type_row.set_model(type_model)
        self._edit_type_row.set_selected(1 if vm["vm_type"] == "monitoring" else 0)

        for row in [self._edit_name_row, self._edit_ip_row, self._edit_user_row,
                    self._edit_admin_user_row, self._edit_admin_pass_row, self._edit_key_row]:
            group.add(row)
            row.connect("changed", lambda _: self._edit_error_label.set_visible(False))
        group.add(self._edit_type_row)

        self._edit_error_label = Gtk.Label(label="")
        self._edit_error_label.set_css_classes(["error"])
        self._edit_error_label.set_margin_start(16)
        self._edit_error_label.set_margin_end(16)
        self._edit_error_label.set_visible(False)

        save_btn = Gtk.Button(label="Save")
        save_btn.set_css_classes(["suggested-action", "pill"])
        save_btn.set_margin_start(16)
        save_btn.set_margin_end(16)
        save_btn.set_margin_top(8)
        save_btn.set_margin_bottom(16)
        save_btn.connect("clicked", self._on_edit_confirmed, vm, dialog)

        content.append(group)
        content.append(self._edit_error_label)
        content.append(save_btn)
        toolbar_view.set_content(content)
        dialog.set_child(toolbar_view)
        dialog.present(self)

    def _on_edit_confirmed(self, _btn, old_vm, dialog):
        name       = self._edit_name_row.get_text().strip()
        ip         = self._edit_ip_row.get_text().strip()
        user       = self._edit_user_row.get_text().strip()
        admin_user = self._edit_admin_user_row.get_text().strip()
        admin_pass = self._edit_admin_pass_row.get_text()
        key        = self._edit_key_row.get_text().strip()
        vm_type    = "monitoring" if self._edit_type_row.get_selected() == 1 else "game"

        if not name or not ip or not user or not admin_user or not admin_pass:
            self._edit_error_label.set_text("All fields are required.")
            self._edit_error_label.set_visible(True)
            return

        if db.slugify(name) in ("all", "ungrouped", "localhost") or \
           (vm_type == "game" and db.slugify(name) == "monitoring"):
            self._edit_error_label.set_text(f"'{name}' is a reserved name, please choose a different name.")
            self._edit_error_label.set_visible(True)
            return

        if vm_type == "monitoring":
            existing = db.get_vms_by_type("monitoring")
            if any(v["id"] != old_vm["id"] for v in existing):
                self._edit_error_label.set_text("A monitoring VM already exists. Only one monitoring VM is supported.")
                self._edit_error_label.set_visible(True)
                return

        try:
            db.update_vm(old_vm["id"], name, ip, user, admin_user, admin_pass, key, vm_type)
        except Exception as e:
            self._edit_error_label.set_text(str(e))
            self._edit_error_label.set_visible(True)
            return

        try:
            new_hostname = db.slugify(name)
            runner.remove_from_inventory(old_vm["hostname"])
            runner.add_to_inventory(new_hostname, ip, user, key, vm_type)
        except Exception as e:
            self._edit_error_label.set_text(f"Saved but inventory update failed: {e}")
            self._edit_error_label.set_visible(True)
            return

        dialog.close()
        self._refresh()

    def _show_error(self, msg):
        self._error_label.set_text(msg)
        self._error_label.set_visible(True)
