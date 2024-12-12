from __future__ import annotations

import pkgutil

EXTENSIONS = [module.name for module in pkgutil.iter_modules(__path__, f"{__package__}.")]
