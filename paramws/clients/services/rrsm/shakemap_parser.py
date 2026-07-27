# -*- coding: utf-8 -*-
from paramws.clients.services.esm.shakemap_parser import ESMShakeMapParser

class RRSMShakeMapParser(ESMShakeMapParser):
    """
    Parse RRSM ShakeMap XML through the shared ESM-compatible implementation.

    The providers use the same response structure, but validation failures
    must identify the service that actually returned the content.
    """

    @staticmethod
    def _invalid_content(expected_content, detail):
        """Build an RRSM/ORFEUS-specific inherited validation error."""
        expected_content = expected_content.replace(
            "ESM ShakeMap",
            "RRSM/ORFEUS ShakeMap",
        )
        return ValueError(
            "RRSM/ORFEUS returned invalid successful content; expected {}. {}"
            .format(expected_content, detail)
        )
