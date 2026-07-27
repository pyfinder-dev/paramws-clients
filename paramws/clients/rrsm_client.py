# -*-coding: utf-8 -*-
from paramws.clients.base_client import BaseClient, MissingRequiredOption
from paramws.clients.services import RRSMShakeMapConnector, RRSMPeakMotionConnector
from paramws.utils.customlogger import logger

class RRSMPeakMotionClient(BaseClient):
    """
    This class encapsulates the worker class for the RRSM peak motion
    web service and its data structure(s).

    The RRSM peak motion web service works with an event id:
    https://orfeus-eu.org/odcws/rrsm/1/peak-motion?eventid=20170524_0000045
    """
    def __init__(self):
        super().__init__()

        # Provider
        self.agency = "ORFEUS"

        # Main service url
        self.base_url = "https://orfeus-eu.org/odcws/rrsm/"

        # Query end point
        self.end_point = "peak-motion"

        # Version of the service, if applicable
        self.version = "1"

        # Options for querying the amplitude data.
        self.amplitude_options = {'eventid': None}

        # Options for querying the event data.
        self.event_options = {'eventid': None}

        # Initialize the web service client.
        if self.get_web_service() is None:
            self.create_web_service()

    def set_event_id(self, event_id):
        """ Set the event id. """
        self.event_options['eventid'] = event_id
        self.amplitude_options['eventid'] = event_id

    def get_event_id(self):
        """ Return the event id. """
        return self.amplitude_options['eventid']

    def get_station_codes(self):
        """ Return the station codes. """
        return self.amplitude_data.get_station_codes()

    def get_stations(self):
        return self.amplitude_data.get_stations()

    def create_web_service(self)->RRSMPeakMotionConnector:
        """ Create the RRSM Peak Motion service connector. """
        self.ws_client = RRSMPeakMotionConnector(
            agency=self.agency, base_url=self.base_url,
            end_point=self.end_point, version=self.version)

        # Return the client for further use in case
        # the method is called directly.
        return self.ws_client

    def query(self, event_id=None, **other_options):
        """ Query the web service for earthquake information. """
        # The event ID selects the single Peak Motion response.
        if event_id is not None:
            self.set_event_id(event_id)
        else:
            raise MissingRequiredOption(
                "Missing required option: event_id")

        # Query the web service for the event information. No need to
        # query twice for amplitudes. RRSM peak motion already returns
        # a json with the station amplitudes and event parameters.
        request_options = dict(self.event_options)
        if 'type' in other_options:
            # Peak Motion does not support type. Passing it to the connector
            # exposes the standard unsupported-option warning and cleaning.
            request_options['type'] = other_options['type']

        _url = self.ws_client.build_url(**request_options)
        _code, _peakmotion_data = self.ws_client.query(url=_url)
        self.set_event_data(_peakmotion_data)
        self.set_station_amplitudes(_peakmotion_data)

        # Return the response code and the data.
        # The amplitude data is the same as the event data for this client.
        return _code, _peakmotion_data, _peakmotion_data


class RRSMShakeMapClient(BaseClient):
    """
    This class encapsulates the worker class for the RRSM shakemap
    web service and its data structure(s).

    RRSM requests event information with ``type=event``. Omitting ``type``
    selects the station representation from the same ShakeMap endpoint.
    e.g. https://orfeus-eu.org/odcws/rrsm/1/shakemap?eventid=20240118_0000062&type=event
    """
    def __init__(self):
        super().__init__()

        # Provider
        self.agency = "ORFEUS"

        # Main service url
        self.base_url = "https://orfeus-eu.org/odcws/rrsm/"

        # Query end point
        self.end_point = "shakemap"

        # Version of the service, if applicable
        self.version = "1"

        # Options for querying the amplitude data.
        self.amplitude_options = {'eventid': None}

        # Options for querying the event data.
        self.event_options = {'eventid': None, 'type': 'event'}

        # Initialize the web service client.
        if self.get_web_service() is None:
            self.create_web_service()

    def set_event_id(self, event_id):
        """ Set the event id. """
        self.event_options['eventid'] = event_id
        self.amplitude_options['eventid'] = event_id

    def get_event_id(self):
        """ Return the event id. """
        return self.amplitude_options['eventid']

    def get_station_codes(self):
        """ Return the station codes. """
        return self.amplitude_data.get_station_codes()

    def get_stations(self):
        return self.amplitude_data.get_stations()

    def create_web_service(self)->RRSMShakeMapConnector:
        """ Create the RRSM ShakeMap service connector. """
        self.ws_client = RRSMShakeMapConnector(
            agency=self.agency, base_url=self.base_url,
            end_point=self.end_point, version=self.version)

        # Return the client for further use in case
        # the method is called directly.
        return self.ws_client

    def query(self, event_id=None, **other_options):
        """ Query the web service for earthquake information. """
        # Both fixed requests use the caller's event ID.
        if event_id is not None:
            self.set_event_id(event_id)
        else:
            raise MissingRequiredOption(
                "Missing required option: event_id")

        # The event and station requests own their type selections because
        # those values determine which response parser can be used. Caller
        # input cannot change type=event for the event request or add type to
        # the station request.
        if 'type' in other_options:
            logger.warning(
                "%s %s ignored fixed option %r with value %r; "
                "the event request keeps type='event' and the station "
                "request keeps type omitted.",
                self.agency,
                self.end_point,
                'type',
                other_options['type'],
            )

        # Query the web service for the event information.
        _url = self.ws_client.build_url(**self.event_options)
        _code, _event_data = self.ws_client.query(url=_url)
        self.set_event_data(_event_data)

        # Query the web service for the amplitude data.
        _url = self.ws_client.build_url(**self.amplitude_options)
        _code, _amplitude_data = self.ws_client.query(url=_url)
        self.set_station_amplitudes(_amplitude_data)

        # Return the response code and the data.
        return _code, _event_data, _amplitude_data
