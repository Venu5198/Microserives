import sys
from pathlib import Path

# Add services/shipping-service and packages/common to sys.path
shipping_service_dir = Path(__file__).resolve().parent.parent
common_pkg_dir = shipping_service_dir.parent.parent / "packages" / "common"

if str(shipping_service_dir) not in sys.path:
    sys.path.insert(0, str(shipping_service_dir))
if str(common_pkg_dir) not in sys.path:
    sys.path.insert(0, str(common_pkg_dir))

