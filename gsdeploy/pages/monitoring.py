import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk


class MonitoringPage(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        self.set_margin_top(24)
        self.set_margin_bottom(24)
        self.set_margin_start(24)
        self.set_margin_end(24)

        status = Adw.StatusPage()
        status.set_icon_name("utilities-system-monitor-symbolic")
        status.set_title("Monitoring")
        status.set_description("Links to Grafana dashboards and service status.")
        self.append(status)
