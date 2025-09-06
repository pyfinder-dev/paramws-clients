# -*- coding: utf-8 -*-
try:
    from paramws.clients.services.baseconnector import BaseWebServiceConnector
    from paramws.clients.services.rrsm.shakemap_connector import RRSMShakeMapConnector
except ImportError:
    from ..baseconnector import BaseWebServiceConnector
    from .shakemap_connector import RRSMShakeMapConnector
