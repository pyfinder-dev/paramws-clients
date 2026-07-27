# -*- coding: utf-8 -*-
import urllib
from paramws.clients.services.baseconnector import BaseWebServiceConnector, InvalidOptionValue
from paramws.clients.services.emsc.feltreport_parser import EMSCFeltReportParser
from paramws.utils.customlogger import logger

class MissingRequiredFieldError(Exception):
    """ Exception raised when a required field is missing. """
    pass

class EMSCFeltReportConnector(BaseWebServiceConnector):
    """
    Connector class for EMSC felt report web service.

    It overrides the following abstract methods:
    - parse_response(self, file_like_obj)
    - get_supported_options(self)
    - is_value_valid(self, option, value)
    - build_url(self, **options)
    """
    def __init__(self, agency='EMSC', end_point='api', version="1.1",
                 base_url='https://www.seismicportal.eu/testimonies-ws/'):
        super().__init__(agency, base_url, end_point, version)

    def get_supported_options(self):
        """
        Return the options available at the EMSC felt-report service.
        """
        return ['unids', 'includeTestimonies']

    def is_value_valid(self, option, value):
        """
        Checks for the value of includeTestimonies option only.
        The options for EMSC are case sensitive.
        """
        _options = {'includeTestimonies': ['true', 'false']}

        if option in _options:
            if value not in _options[option]:
                return False
        return True

    def build_url(self, **options):
        """
        Build the URL for the felt reports web service.
        The URL structure is:
        https://www.seismicportal.eu/testimonies-ws/api/search?unids=[20201230_0000049]&includeTestimonies=true
        """
        if not options:
            # If options are not defined, create an empty dict.
            # No options means we will query the whole event database
            # from the EMSC for the event information. The service
            # will return 500 records by default.
            options = {}

        # The canonical spelling always wins. Without it, the first accepted
        # legacy spelling below supplies the normalized value; warning about
        # later duplicates prevents ambiguous caller input from being replaced
        # silently.
        has_include_testimonies = 'includeTestimonies' in options
        for alias in ['includetestimonies', 'IncludeTestimonies',
                      'Includetestimonies']:
            if alias not in options:
                continue

            value = options.pop(alias)
            if not has_include_testimonies:
                options['includeTestimonies'] = value
                has_include_testimonies = True
                continue

            logger.warning(
                "%s %s ignored duplicate option %r with value %r; "
                "includeTestimonies value %r remains in effect.",
                self.get_agency(),
                self.get_end_point(),
                alias,
                value,
                options['includeTestimonies'],
            )

        # Check for the "unids" option. It needs to passed as a list.
        # If it is a string, convert it to a string representation of
        # a list. The web service expects the event id to be in brackets.
        if 'unids' in options:
            if isinstance(options['unids'], str):
                # Check if the option string is already in a list
                # format on both ends.
                if options['unids'][0] != '[':
                    options['unids'] = '[' + options['unids']
                if options['unids'][-1] != ']':
                    options['unids'] = options['unids'] + ']'

                # Clean up white spaces and quotes that may have been
                # added by mistake.
                options['unids'] = options['unids'].replace(' ', '')
                options['unids'] = options['unids'].replace("'", '')
                options['unids'] = options['unids'].replace('"', '')

            elif isinstance(options['unids'], list):
                pass

            else:
                raise InvalidOptionValue("unids", options['unids'])

        # Validate the options the first against the
        # list of supported options
        options = self.validate_options(**options)

        # Safety check for the base URL.
        if self.base_url and self.base_url[-1] != "/":
            self.base_url += "/"

        # EMSC expects the surrounding unids brackets to remain visible.
        # Delimiters inside the bracketed event value must still be encoded
        # as data so they cannot introduce another query parameter.
        options = urllib.parse.urlencode(
            options, safe='[]', encoding='utf-8')

        # Combine the URL
        self.combined_url = \
            f"{self.base_url}{self.end_point}/search?{options}"

        return self.combined_url


    def parse_response(self, file_like_obj=None, options=None):
        """ Parse the response from felt reports web service. """
        # Check if testimonies are requested. The default
        # on the web service is False.
        if 'includeTestimonies' in options:
            if options['includeTestimonies'].lower() == 'true':
                testimonies_included = True
            else:
                testimonies_included = False
        else:
            testimonies_included = False

        if file_like_obj:
            parser = EMSCFeltReportParser()

            if testimonies_included:
                # Intensity data with testimonies. This will be a zip
                # file containing the intensity data in csv format.
                data = parser.parse_testimonies(file_like_obj)

            else:
                # Event information without testimonies.
                # This will be in json format.
                data = parser.parse(file_like_obj)

            self.set_data(data)

        return self.get_data()
