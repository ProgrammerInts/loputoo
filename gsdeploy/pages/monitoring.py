import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk, Gio

import gsdeploy.database as db


class MonitoringPage(Gtk.ScrolledWindow):
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

        monitoring_vms = db.get_vms_by_type("monitoring")

        if not monitoring_vms:
            status = Adw.StatusPage()
            status.set_icon_name("utilities-system-monitor-symbolic")
            status.set_title("No monitoring VM")
            status.set_description("Add a VM with type 'monitoring' and deploy monitoring to get started.")
            status.set_vexpand(True)
            self._content.append(status)
            return

        if db.get_setting("grafana_password_changed") != "1":
            banner = Adw.Banner()
            banner.set_title("Change the default Grafana password after first login.")
            banner.set_button_label("Dismiss")
            banner.set_revealed(True)
            banner.connect("button-clicked", self._dismiss_grafana_notice)
            self._content.append(banner)

        for vm in monitoring_vms:
            ip = vm["ip"]

            group = Adw.PreferencesGroup(
                title=vm["name"],
                description=f"Monitoring services at {ip}",
            )

            grafana_url = f"http://{ip}:3000"
            prometheus_url = f"http://{ip}:9090"

            for label, url, subtitle in [
                ("Grafana", grafana_url, "Dashboards and log exploration  ·  default login: admin"),
                ("Prometheus", prometheus_url, "Metrics and query explorer"),
            ]:
                row = Adw.ActionRow(title=label, subtitle=subtitle)
                row.set_activatable(True)
                row.connect("activated", self._open_url, url)

                url_label = Gtk.Label(label=url)
                url_label.set_css_classes(["dim-label", "caption"])
                url_label.set_valign(Gtk.Align.CENTER)
                row.add_suffix(url_label)

                icon = Gtk.Image.new_from_icon_name("go-next-symbolic")
                icon.set_valign(Gtk.Align.CENTER)
                row.add_suffix(icon)

                group.add(row)

            self._content.append(group)

    def _dismiss_grafana_notice(self, _banner):
        db.set_setting("grafana_password_changed", "1")
        self._refresh()

    def _open_url(self, _row, url):
        Gio.AppInfo.launch_default_for_uri(url, None)
