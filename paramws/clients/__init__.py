# -*- coding: utf-8 -*-
"""
Public API for web service clients and their related data structures.
Import from here for convenience, rather than deep submodules.
"""

# Manager classes for the web service clients
from .esm_client import ESMShakeMapClient
from .rrsm_client import RRSMShakeMapClient, RRSMPeakMotionClient
from .emsc_client import EMSCFeltReportClient

# Data structures from the services module
from .services import (
    PeakMotionData,
    ShakeMapEventData,
    FeltReportEventData,
    FeltReportIntensityData,
    PeakMotionStationData,
    PeakMotionChannelData,
    ShakeMapComponentNode,
    ShakeMapStationAmplitudes,
    ShakeMapStationNode,
)

__all__ = [
    # Client classes
    "ESMShakeMapClient",
    "RRSMShakeMapClient",
    "RRSMPeakMotionClient",
    "EMSCFeltReportClient",

    # Data structures
    "PeakMotionData",
    "ShakeMapEventData",
    "FeltReportEventData",
    "FeltReportIntensityData",
    "PeakMotionStationData",
    "PeakMotionChannelData",
    "ShakeMapComponentNode",
    "ShakeMapStationAmplitudes",
    "ShakeMapStationNode",
]
