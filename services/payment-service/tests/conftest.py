import sys
from pathlib import Path

# Add services/payment-service and packages/common to sys.path
payment_service_dir = Path(__file__).resolve().parent.parent
common_pkg_dir = payment_service_dir.parent.parent / "packages" / "common"

if str(payment_service_dir) not in sys.path:
    sys.path.insert(0, str(payment_service_dir))
if str(common_pkg_dir) not in sys.path:
    sys.path.insert(0, str(common_pkg_dir))

