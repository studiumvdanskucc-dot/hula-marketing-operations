"""HULA Marketing Operations application services.

The package is deliberately independent from the existing trend application UI.
It may read approved trend snapshots, but a failure here must never stop
``app.py`` from starting.
"""

from .config import MarketingSettings, load_marketing_settings

__all__ = ["MarketingSettings", "load_marketing_settings"]
