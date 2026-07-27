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

    def set_station_amplitudes(self, peak_motion):
        """ Set the peak-motion dataset for the current event. """
        self.datasets["peak_motion"] = peak_motion

    def get_station_amplitudes(self):
        """ Return the peak-motion dataset for the current event. """
        return self.datasets.get("peak_motion")

    def get_station_codes(self):
        """ Return the station codes. """
        return self.get_station_amplitudes().get_station_codes()

    def get_stations(self):
        return self.get_station_amplitudes().get_stations()

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
        # The one provider response supplies both event information and peak
        # motion measurements. Reset both public representations, connector
        # response data, and stored identifiers before validating this call so
        # even a missing-event failure cannot expose an earlier result.
        self._reset_query_state(("peak_motion",))
        self.event_options['eventid'] = None
        self.amplitude_options['eventid'] = None

        if event_id is None:
            raise MissingRequiredOption(
                "Missing required option: event_id")

        self.set_event_id(event_id)
        request_options = dict(self.event_options)

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

        # Peak Motion supports only eventid. Pass every remaining caller name,
        # including type, through the connector so unsupported options receive
        # the standard provider-specific warning and cannot reach the URL.
        query_options = self.ws_client.validate_options(**query_options)
        request_options.update(query_options)

        request_url = self.ws_client.build_url(**request_options)
        code, peak_motion_data = self.ws_client.query(url=request_url)

        if code is not None and 200 <= code < 300:
            # The parser deliberately keeps the provider's combined
            # measurement hierarchy while exposing its nested event model as
            # the conceptually separate event result.
            self.set_event_data(peak_motion_data.get_event_data())
            self.set_station_amplitudes(peak_motion_data)
        else:
            logger.error(
                "provider='ORFEUS' url=%s status=%r dataset=peak_motion "
                "outcome=failed",
                request_url,
                code,
            )

        return code, self.event_data, self.datasets


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
        # Results, connector response data, and event identifiers belong only
        # to the current event-scoped query. Reset them before validating the
        # required identifier so a failed call cannot expose older data.
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

        # The event and station requests own their type selections because
        # those values determine which response parser can be used. Caller
        # input cannot change type=event for the event request or add type to
        # the station request.
        if 'type' in query_options:
            logger.warning(
                "%s %s ignored fixed option %r with value %r; "
                "the event request keeps type='event' and the station "
                "request keeps type omitted.",
                self.get_agency(),
                self.get_end_point(),
                'type',
                query_options.pop('type'),
            )

        # RRSM currently has no caller-controlled ShakeMap selection after
        # removing the two authoritative native fields. Still pass every
        # remaining name through connector validation so unsupported input is
        # warned about and removed consistently with direct connector use.
        self.ws_client.validate_options(**query_options)

        overall_code = 200
        event_parse_error = None

        # Query the web service for the event information.
        event_url = self.ws_client.build_url(**event_options)
        try:
            event_code, event_data = self.ws_client.query(url=event_url)
        except ValueError as error:
            # The station representation is an independent request. Preserve
            # the event validation failure while still attempting to retain
            # useful station data.
            event_parse_error = error
        else:
            if event_code is not None and 200 <= event_code < 300:
                self.set_event_data(event_data)
            else:
                overall_code = event_code
                logger.error(
                    "provider='ORFEUS' url=%s status=%r dataset=event "
                    "outcome=failed",
                    event_url,
                    event_code,
                )

        # Query the independent station-amplitude representation even when
        # the earlier event request failed over HTTP or during parsing.
        amplitude_url = self.ws_client.build_url(**amplitude_options)
        try:
            amplitude_code, amplitude_data = self.ws_client.query(
                url=amplitude_url)
        except ValueError:
            # If both responses fail validation, the event failure occurred
            # first in the client's defined logical request order.
            if event_parse_error is not None:
                raise event_parse_error
            raise
        if amplitude_code is not None and 200 <= amplitude_code < 300:
            self.set_station_amplitudes(amplitude_data)
        else:
            if overall_code == 200:
                overall_code = amplitude_code
            logger.error(
                "provider='ORFEUS' url=%s status=%r "
                "dataset=station_amplitudes outcome=failed",
                amplitude_url,
                amplitude_code,
            )

        if event_parse_error is not None:
            raise event_parse_error

        return overall_code, self.event_data, self.datasets
