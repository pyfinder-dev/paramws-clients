# -*-coding: utf-8 -*-
from paramws.clients.base_client import BaseClient, MissingRequiredOption
from paramws.clients.services import ESMShakeMapConnector
from paramws.utils.customlogger import logger

class ESMShakeMapClient(BaseClient):
    """ 
    This class encapsulates the actual ESM shakemap web service 
    client and respective data structure(s). The purpose of this 
    class is to provide a single interface to the ESM web services. 
    The client classes are defined in the clients/services directory.
    """
    def __init__(self):
        super().__init__()

        # Provider
        self.agency = "ESM"
        
        # Main service url
        self.base_url = "https://esm-db.eu/esmws/"
        
        # Query end point
        self.end_point = "shakemap" 
        
        # Version of the service, if applicable
        self.version = "1"

        # Options for querying the event data.
        self.event_options = {'eventid': None, 'catalog': 'EMSC', 
                              'format': 'event', 'flag': '0', 
                              'encoding': 'UTF-8'}
        
        # Options for querying the amplitude data.
        self.amplitude_options = {'eventid': None, 'catalog': 'EMSC', 
                                  'format': 'event_dat', 'flag': '0', 
                                  'encoding': 'UTF-8'}
        
        # Initialize the web service client.
        if self.get_web_service() is None:
            self.create_web_service()
                
    def set_event_id(self, event_id):
        """ Set the event id. """
        self.event_options['eventid'] = event_id
        self.amplitude_options['eventid'] = event_id

    def get_event_id(self):
        """ Return the event id. """
        return self.event_options['eventid']

    def set_station_amplitudes(self, station_amplitudes):
        """ Set the station amplitudes for the current event. """
        self.datasets["station_amplitudes"] = station_amplitudes

    def get_station_amplitudes(self):
        """ Return the station amplitudes for the current event. """
        return self.datasets.get("station_amplitudes")
    
    def get_station_codes(self):
        """ Return the station codes. """
        return self.get_station_amplitudes().get_station_codes()
    
    def get_stations(self):
        return self.get_station_amplitudes().get_stations()
    
    def get_supported_catalogs(self):
        """ Return the list of supported catalogs. """
        return ['ESM', 'ISC', 'USGS', 'EMSC', 'INGV']
    
    def set_catalog(self, catalog):
        """ Set the catalog. Always defaults to EMSC when 
        the catalog is not supported. This is the same
        behavior as in the ESM web service. """
        if catalog not in self.get_supported_catalogs():
            catalog = 'EMSC'

        self.event_options['catalog'] = catalog
        self.amplitude_options['catalog'] = catalog

    def include_problematic_data(self, include=False):
        """ 
        Include problematic data in the output. The default is False.
        The default in the options for are also False (flag=0)
        """
        # Accept the actual value of the 'flag' option
        # as defined from the method interface.
        if isinstance(include, str):
            if include.lower() == 'all':
                include = True
            else:
                include = False

        # Set the 'flag' option
        if include:
            self.event_options['flag'] = 'all'
            self.amplitude_options['flag'] = 'all'
        else:
            self.event_options['flag'] = '0'
            self.amplitude_options['flag'] = '0'
        
    def create_web_service(self)->ESMShakeMapConnector:
        """ Creates a new ESM shakemap web service client. """
        self.ws_client = ESMShakeMapConnector(
            agency=self.agency, base_url=self.base_url, 
            end_point=self.end_point, version=self.version)

        # Return the client for further use in case
        # the method is called directly.
        return self.ws_client
    
    def query(self, event_id=None, **other_options):
        """ Query the web service for earthquake information. """
        # Results and event identifiers belong only to the current query.
        # Public option methods such as set_catalog() remain persistent
        # configuration, while keyword options below are applied to local
        # copies so one call cannot change the next call's defaults.
        self._reset_query_state(("station_amplitudes",))
        self.event_options['eventid'] = None
        self.amplitude_options['eventid'] = None

        if event_id is None:
            raise MissingRequiredOption(
                "Missing required option: event_id")

        self.set_event_id(event_id)
        event_options = dict(self.event_options)
        amplitude_options = dict(self.amplitude_options)

        query_options = dict(other_options)
        if 'eventid' in query_options:
            logger.warning(
                "%s %s ignored caller override of fixed option %r with "
                "value %r; explicit event_id %r remains in effect.",
                self.get_agency(),
                self.get_end_point(),
                'eventid',
                query_options.pop('eventid'),
                event_id,
            )
        if 'format' in query_options:
            logger.warning(
                "%s %s ignored caller override of fixed option %r with "
                "value %r; event format %r and station-amplitude format %r "
                "remain in effect.",
                self.get_agency(),
                self.get_end_point(),
                'format',
                query_options.pop('format'),
                event_options['format'],
                amplitude_options['format'],
            )

        # The connector remains the authority for native ESM option names and
        # values. Applying its cleaned result to local copies preserves public
        # method configuration while preventing query keywords from leaking.
        query_options = self.ws_client.validate_options(**query_options)
        for option in ('catalog', 'flag', 'encoding'):
            if option in query_options:
                event_options[option] = query_options[option]
                amplitude_options[option] = query_options[option]

        overall_code = 200
        event_parse_error = None

        # Query the web service for the event information.
        event_url = self.ws_client.build_url(**event_options)
        try:
            event_code, event_data = self.ws_client.query(url=event_url)
        except ValueError as error:
            # Parsing a successful event response must not make the separate
            # station endpoint dependent on that response. Keep the original
            # exception so it can be re-raised after the station attempt.
            event_parse_error = error
        else:
            if event_code is not None and 200 <= event_code < 300:
                self.set_event_data(event_data)
            else:
                overall_code = event_code
                logger.error(
                    "provider='ESM' url=%s status=%r dataset=event "
                    "outcome=failed",
                    event_url,
                    event_code,
                )

        # Station amplitudes are independent of the event response. Attempt
        # this request even when the provider rejected the earlier event
        # request, retaining any station data that can still be parsed.
        amplitude_url = self.ws_client.build_url(**amplitude_options)
        try:
            amplitude_code, amplitude_data = self.ws_client.query(
                url=amplitude_url)
        except ValueError:
            # When both successful responses are invalid, preserve the first
            # parse failure in the client's defined request order.
            if event_parse_error is not None:
                raise event_parse_error
            raise
        if amplitude_code is not None and 200 <= amplitude_code < 300:
            self.set_station_amplitudes(amplitude_data)
        else:
            if overall_code == 200:
                overall_code = amplitude_code
            logger.error(
                "provider='ESM' url=%s status=%r "
                "dataset=station_amplitudes outcome=failed",
                amplitude_url,
                amplitude_code,
            )

        if event_parse_error is not None:
            raise event_parse_error

        return overall_code, self.event_data, self.datasets
