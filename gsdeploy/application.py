import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio

from gsdeploy.window import GsDeployWindow
from gsdeploy.database import init_db
from gsdeploy.ansible_runner import sync_inventory_from_db


class GsDeployApplication(Adw.Application):
    def __init__(self):
        super().__init__(
            application_id="io.github.gsdeploy",
            flags=Gio.ApplicationFlags.NON_UNIQUE,
        )
        self.connect("activate", self.on_activate)

    def on_activate(self, app):
        init_db()
        sync_inventory_from_db()
        win = GsDeployWindow(application=app)
        win.present()
