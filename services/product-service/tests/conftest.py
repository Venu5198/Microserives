import sys
from pathlib import Path

# Add services/product-service and packages/common to sys.path
product_service_dir = Path(__file__).resolve().parent.parent
common_pkg_dir = product_service_dir.parent.parent / "packages" / "common"

if str(product_service_dir) not in sys.path:
    sys.path.insert(0, str(product_service_dir))
if str(common_pkg_dir) not in sys.path:
    sys.path.insert(0, str(common_pkg_dir))

