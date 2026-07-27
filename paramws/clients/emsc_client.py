# -*-coding: utf-8 -*-
from paramws.clients.base_client import BaseClient, MissingRequiredOption
from paramws.clients.services import EMSCFeltReportConnector
from paramws.clients.services.feltreport_data import FeltReportIntensityData
from paramws.utils.customlogger import logger

class EMSCFeltReportClient(BaseClient):
    """
    This class encapsulates the worker class for the EMSC felt report
    web service and its data structure(s), both for intensities and
    event data. 
    """
    def __init__(self):
        super().__init__()
        
        # Provider
        self.agency = "EMSC"
        
        # Main service url
        self.base_url = "https://www.seismicportal.eu/testimonies-ws/"
        
        # Query end point
        self.end_point = "api"
        
        # Version of the service, if applicable
        self.version = "1.1"
        
        # Options for querying the felt reports. The web service
        # will return a zip file.
        self.felt_report_options = {'includeTestimonies': 'true'}

        # Options for querying the event data. The web service
        # will return a json file.
        self.event_data_options = {'includeTestimonies': 'false'}
        
        # Initialize the web service client.
        if self.get_web_service() is None:
            self.create_web_service()

    def set_event_id(self, event_id):
        """ Set the event id. """
        self.felt_report_options['unids'] = "[" + event_id + "]"
        self.event_data_options['unids'] = "[" + event_id + "]"

    def get_event_id(self):
        """
        Return the current event id without the provider-required brackets.

        Query state is reset before required options are checked, so no event
        identifier is a valid state after a failed query.
        """
        event_id = self.felt_report_options.get('unids')
        if event_id is None:
            return None
        return event_id.replace('[', '').replace(']', '')

    def set_feltreports(self, feltreports):
        """ Set the felt intensities for the current event. """
        self.datasets["felt_intensities"] = feltreports
    
    def create_web_service(self)->EMSCFeltReportConnector:
        """ Creates a new EMSC felt report web service client. """
        self.ws_client = EMSCFeltReportConnector(
            agency=self.agency, base_url=self.base_url, 
            end_point=self.end_point, version=self.version)

        # Return the client for further use in case
        # the method is called directly.
        return self.ws_client
            
    
    def get_feltreports(self):
        """ Return the felt reports. Felts reports are designed to have
        more than one event. The event id is the key for the dictionary 
        for this event."""
        feltreports = self.datasets.get("felt_intensities")
        if feltreports is None:
            return None

        # The parser keeps all event entries in one established intensity
        # model. This semantic getter continues to expose only the current
        # event's view, also accepting the former raw-dictionary input to
        # preserve the meaningful behavior of set_feltreports().
        if isinstance(feltreports, FeltReportIntensityData):
            feltreport_data = feltreports.get_data()
        else:
            feltreport_data = feltreports

        event_id = self.get_event_id()
        if event_id is None or event_id not in feltreport_data:
            return None
        feltreport_dict = feltreport_data[event_id]
        
        return FeltReportIntensityData(feltreport_dict)
    
    def query(self, event_id=None, **other_options):
        """ Query the web service for earthquake information. """
        # Results, connector response data, event identifiers, and query
        # options describe only this call. Reset all of them before checking
        # the required identifier so a failed query cannot expose old state.
        self._reset_query_state(("felt_intensities",))
        self.felt_report_options.clear()
        self.felt_report_options.update({'includeTestimonies': 'true'})
        self.event_data_options.clear()
        self.event_data_options.update({'includeTestimonies': 'false'})

        if event_id is None:
            raise MissingRequiredOption(
                "Missing required option: event_id")

        self.set_event_id(event_id)
        felt_report_options = dict(self.felt_report_options)
        event_data_options = dict(self.event_data_options)

        # These native options determine both the requested event and which
        # response parser the connector uses. The explicit event_id and the
        # two fixed testimony selections must remain authoritative.
        query_options = dict(other_options)
        fixed_include_names = (
            'includeTestimonies',
            'includetestimonies',
            'IncludeTestimonies',
            'Includetestimonies',
        )
        if 'unids' in query_options:
            logger.warning(
                "%s %s ignored caller override of fixed option %r with "
                "value %r; explicit event_id %r remains in effect.",
                self.get_agency(),
                self.get_end_point(),
                'unids',
                query_options.pop('unids'),
                event_id,
            )
        for option in fixed_include_names:
            if option not in query_options:
                continue
            logger.warning(
                "%s %s ignored caller override of fixed option %r with "
                "value %r; felt intensities keep includeTestimonies='true' "
                "and event data keeps includeTestimonies='false'.",
                self.get_agency(),
                self.get_end_point(),
                option,
                query_options.pop(option),
            )

        # No remaining EMSC option is caller-controlled for this two-response
        # operation. Still validate every supplied name so unsupported input
        # receives the connector's provider-specific warning.
        self.ws_client.validate_options(**query_options)

        overall_code = 200
        felt_parse_error = None

        # Felt intensities are first in the defined logical request order.
        felt_url = self.ws_client.build_url(**felt_report_options)
        try:
            felt_code, feltreport_data = self.ws_client.query(url=felt_url)
        except ValueError as error:
            # Event data is independent. Retain this first parse failure while
            # still attempting to populate the useful event result.
            felt_parse_error = error
        else:
            if felt_code is not None and 200 <= felt_code < 300:
                self.set_feltreports(feltreport_data)
            else:
                overall_code = felt_code
                logger.error(
                    "provider='EMSC' url=%s status=%r "
                    "dataset=felt_intensities outcome=failed",
                    felt_url,
                    felt_code,
                )

        # Event data is the second independent response and remains separate
        # from the felt-intensity dataset.
        event_url = self.ws_client.build_url(**event_data_options)
        try:
            event_code, event_data = self.ws_client.query(url=event_url)
        except ValueError:
            # If both successful responses are invalid, the intensity failure
            # occurred first and is therefore the one the caller receives.
            if felt_parse_error is not None:
                raise felt_parse_error
            raise
        if event_code is not None and 200 <= event_code < 300:
            self.set_event_data(event_data)
        else:
            if overall_code == 200:
                overall_code = event_code
            logger.error(
                "provider='EMSC' url=%s status=%r dataset=event "
                "outcome=failed",
                event_url,
                event_code,
            )

        if felt_parse_error is not None:
            raise felt_parse_error

        return overall_code, self.event_data, self.datasets
