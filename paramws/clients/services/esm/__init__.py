# -*- coding: utf-8 -*-
try:
    from paramws.clients.services.baseconnector import BaseWebServiceConnector
    from paramws.clients.services.esm.shakemap_connector import ESMShakeMapConnector
except ImportError:
    from ..baseconnector import BaseWebServiceConnector
    from .shakemap_connector import ESMShakeMapConnector
