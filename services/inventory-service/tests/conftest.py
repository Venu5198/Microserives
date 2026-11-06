import sys
from pathlib import Path

# Add services/inventory-service and packages/common to sys.path
inventory_service_dir = Path(__file__).resolve().parent.parent
common_pkg_dir = inventory_service_dir.parent.parent / "packages" / "common"

if str(inventory_service_dir) not in sys.path:
    sys.path.insert(0, str(inventory_service_dir))
if str(common_pkg_dir) not in sys.path:
    sys.path.insert(0, str(common_pkg_dir))

