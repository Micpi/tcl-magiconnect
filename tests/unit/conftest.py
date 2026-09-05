"""Load the transport package without importing Home Assistant lifecycle code."""

import sys
from pathlib import Path
from types import ModuleType

package = ModuleType("magiconnect_wire")
package.__path__ = [str(Path(__file__).resolve().parents[2] / "custom_components/tcl_magiconnect")]
sys.modules[package.__name__] = package
