import sys
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gsdeploy.application import GsDeployApplication

def main():
    app = GsDeployApplication()
    return app.run(sys.argv)

if __name__ == "__main__":
    sys.exit(main())
