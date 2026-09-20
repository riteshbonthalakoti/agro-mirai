"""Data-acquisition adapters (Module 03).

The public surface Module 05+ depends on: the :class:`Adapter` interface,
its :class:`FieldInput` argument, the typed error hierarchy, and the three
concrete adapters. Import these; never a raw ``requests``/``ee`` client.
"""
from .base import (
    Adapter,
    AcquisitionError,
    FieldInput,
    SourceResponseError,
    SourceUnavailableError,
)
from .earth_engine import NDVIAdapter
from .open_meteo import WeatherAdapter
from .soilgrids import SoilAdapter

__all__ = [
    "Adapter",
    "AcquisitionError",
    "FieldInput",
    "SourceResponseError",
    "SourceUnavailableError",
    "WeatherAdapter",
    "SoilAdapter",
    "NDVIAdapter",
]
