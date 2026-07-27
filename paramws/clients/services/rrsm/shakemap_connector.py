# -*- coding: utf-8 -*-
import urllib
from paramws.clients.services.baseconnector import BaseWebServiceConnector
from paramws.clients.services.rrsm.shakemap_parser import RRSMShakeMapParser

class RRSMShakeMapConnector(BaseWebServiceConnector):
    """
    Class for the RRSM ShakeMap web service connector.

    RRSM's URL shape is small enough to keep explicit here. This connector and
    the Peak Motion connector are direct siblings because they represent
    distinct provider endpoints with different supported options.
    """
    def __init__(self, agency="ORFEUS", base_url="https://orfeus-eu.org/odcws/rrsm/",
                 end_point="shakemap", version="1"):
        super().__init__(agency, base_url, end_point, version)

    def parse_response(self, file_like_obj=None, options=None):
        """ Parse the data returned by the web service. """
        if file_like_obj:
            parser = RRSMShakeMapParser()

            if 'type' in options and options['type'] == "event":
                data = parser.parse_earthquake(file_like_obj)
            else:
                data = parser.parse(file_like_obj)

            self.set_data(data)

        return self.get_data()

    def get_supported_options(self):
        """
        Return the options available at the RRSM ShakeMap service.
        """
        return ['eventid', 'type']

    def is_value_valid(self, option, value):
        """
        Check the only restricted RRSM ShakeMap option value.

        Event data uses ``type=event``. Station data uses no ``type`` option.
        """
        if option == 'type' and value != 'event':
            return False
        return True

    def build_url(self, **options):
        """
        RRSM uses inverted service and version order in the URL. Also,
        there is no "query" key word.
        e.g. https://orfeus-eu.org/odcws/rrsm/1/shakemap?eventid=20170524_0000045
        """
        if not options:
            options = {}

        # Validate the options the first against the
        # list of supported options
        options = self.validate_options(**options)

        # Safety check for the base URL.
        if self.base_url and self.base_url[-1] != "/":
            self.base_url += "/"

        # Embedded delimiters belong to the RRSM event ID value and must not
        # be interpreted as additional query syntax.
        options = urllib.parse.urlencode(options, encoding='utf-8')

        # Combine the URL
        self.combined_url = \
            f"{self.base_url}{self.version}/{self.end_point}?{options}"

        return self.combined_url
