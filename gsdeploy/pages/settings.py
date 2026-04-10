import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

import gsdeploy.database as db


class SettingsPage(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        inner.set_margin_top(24)
        inner.set_margin_bottom(24)
        inner.set_margin_start(24)
        inner.set_margin_end(24)

        debug_group = Adw.PreferencesGroup(
            title="Ansible",
            description="Options for Ansible playbook execution",
        )

        self._debug_row = Adw.SwitchRow(title="Debug Mode", subtitle="Pass -v to Ansible for verbose output in provisioning and deployment logs")
        self._debug_row.set_active(db.get_setting("ansible_debug", "0") == "1")
        self._debug_row.connect("notify::active", self._on_debug_toggled)
        debug_group.add(self._debug_row)

        inner.append(debug_group)
        self.append(inner)

    def _on_debug_toggled(self, row, _param):
        db.set_setting("ansible_debug", "1" if row.get_active() else "0")
