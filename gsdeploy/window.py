import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

from gsdeploy.pages.guide import GuidePage
from gsdeploy.pages.dashboard import DashboardPage
from gsdeploy.pages.vm_manager import VMManagerPage
from gsdeploy.pages.deploy_wizard import DeployWizardPage
from gsdeploy.pages.monitoring import MonitoringPage


NAV_ITEMS = [
    ("Guide",            "help-about-symbolic",              GuidePage),
    ("Dashboard",        "org.gnome.SystemMonitor-symbolic",  DashboardPage),
    ("Virtual Machines", "computer-symbolic",                VMManagerPage),
    ("Deploy Server",    "system-run-symbolic",              DeployWizardPage),
    ("Monitoring",       "utilities-system-monitor-symbolic", MonitoringPage),
]


class GsDeployWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_title("GSDeploy")
        self.set_default_size(960, 680)

        self._pages = {}
        self._build_ui()

    def _build_ui(self):
        self.split_view = Adw.NavigationSplitView()

        # --- Sidebar ---
        sidebar_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        sidebar_header = Adw.HeaderBar()
        sidebar_header.set_show_end_title_buttons(False)
        sidebar_box.append(sidebar_header)

        self.nav_list = Gtk.ListBox()
        self.nav_list.set_css_classes(["navigation-sidebar"])
        self.nav_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.nav_list.connect("row-selected", self._on_nav_selected)

        for label, icon, _ in NAV_ITEMS:
            row = Adw.ActionRow(title=label)
            row.add_prefix(Gtk.Image.new_from_icon_name(icon))
            row.set_activatable(True)
            self.nav_list.append(row)

        sidebar_box.append(self.nav_list)

        sidebar_page = Adw.NavigationPage.new(sidebar_box, "GSDeploy")
        self.split_view.set_sidebar(sidebar_page)

        # --- Content ---
        self.content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.content_header = Adw.HeaderBar()
        self.content_box.append(self.content_header)

        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.content_box.append(self.stack)

        for i, (label, _, PageClass) in enumerate(NAV_ITEMS):
            page = PageClass()
            self._pages[i] = page
            self.stack.add_named(page, str(i))

        self.content_nav_page = Adw.NavigationPage.new(self.content_box, "Dashboard")
        self.split_view.set_content(self.content_nav_page)

        self.set_content(self.split_view)

        # Select first item
        self.nav_list.select_row(self.nav_list.get_row_at_index(0))

    def _on_nav_selected(self, listbox, row):
        if row is None:
            return
        idx = row.get_index()
        label = NAV_ITEMS[idx][0]
        self.stack.set_visible_child_name(str(idx))
        self.content_nav_page.set_title(label)
