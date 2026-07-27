# -*- coding: utf-8 -*-
import urllib
from paramws.clients.services.baseconnector import BaseWebServiceConnector
from paramws.clients.services.rrsm.peakmotion_parser import RRSMPeakMotionParser

class RRSMPeakMotionConnector(BaseWebServiceConnector):
    """
    This class is web service client for the RRSM peak motions.
    The RRSM peak motion web service complementary to the RRSM shakemap web
    service, but also includes the event information in addition to the PGA
    and PGV values. Spectral amplitudes are not included. The end point is
    'peak-motion'. Its small URL builder remains explicit because Peak Motion
    and ShakeMap support different option contracts despite similar URL
    shapes.
    """
    def __init__(self, agency="ORFEUS", base_url="https://orfeus-eu.org/odcws/rrsm/",
                 end_point="peak-motion", version="1"):
        super().__init__(agency, base_url, end_point, version)

    def get_supported_options(self):
        """
        Return the options available at the RRSM Peak Motion service.
        """
        return ['eventid']

    def is_value_valid(self, option, value):
        """
        Accept any event identifier value.

        Unsupported names, including ``type``, are removed before this
        endpoint-specific value check.
        """
        return True

    def build_url(self, **options):
        """
        Build an RRSM Peak Motion URL with its endpoint-specific options.

        The explicit builder keeps Peak Motion independent from the concrete
        ShakeMap connector while preserving RRSM parameter order.
        """
        if not options:
            options = {}

        options = self.validate_options(**options)

        if self.base_url and self.base_url[-1] != "/":
            self.base_url += "/"

        # Event identifiers are values, so embedded delimiters are encoded
        # instead of becoming new query parameters.
        options = urllib.parse.urlencode(options, encoding='utf-8')
        self.combined_url = \
            f"{self.base_url}{self.version}/{self.end_point}?{options}"

        return self.combined_url

    def parse_response(self, file_like_obj=None, options=None):
        """ Parse the data returned by the web service. """
        if file_like_obj:
            parser = RRSMPeakMotionParser()

            data = parser.parse(file_like_obj)

            self.set_data(data)

        return self.get_data()
