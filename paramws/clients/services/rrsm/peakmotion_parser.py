# -*- coding: utf-8 -*-
import json
from paramws.clients.services.baseparser import BaseParser
from paramws.clients.services.peakmotion_data import (
    PeakMotionData, PeakMotionStationData, 
    PeakMotionChannelData, PeakMotionEventData)

class RRSMPeakMotionParser(BaseParser):
    """ Parses the peak motion data from RRSM. The peak motion
    data includes event information as well as the PGA and PGV """
    EVENT_KEYS = (
        "event-id", "event-time", "event-magnitude", "magnitude-type",
        "event-depth", "event-latitude", "event-longitude", "review-type",
        "event-location-reference", "event-magnitude-reference",
    )
    STATION_KEYS = (
        "network-code", "station-code", "location-code",
        "station-latitude", "station-longitude", "station-elevation",
        "epicentral-distance", "review-type",
    )
    CHANNEL_KEYS = (
        "channel-code", "pga-value", "pgv-value", "sensor-azimuth",
        "sensor-dip", "sensor-depth", "low-cut-corner", "high-cut-corner",
    )

    def __init__(self):
        super().__init__()

    def validate(self, data):
        """Check the content of the data."""
        return (
            isinstance(data, (str, bytes, bytearray))
            or (data is not None and hasattr(data, "read"))
        )

    @staticmethod
    def _require_fields(record, required_fields, structure):
        """Require the provider fields already consumed by this parser."""
        if not isinstance(record, dict):
            raise ValueError(
                "RRSM Peak Motion response is invalid: expected {} to be "
                "an object, got {}.".format(
                    structure, type(record).__name__))

        for field in required_fields:
            if field not in record:
                raise ValueError(
                    "RRSM Peak Motion response is invalid: expected {} "
                    "field {!r}.".format(structure, field))
    
    def parse(self, data)->PeakMotionData:
        """
        Parse the data. For the peak-motion end point, the data is
        already in json format (a list of jsons). So, this parser 
        just breaks the content into logical components.
        """
        if not self.validate(data):
            raise ValueError(
                "RRSM Peak Motion response is invalid: expected readable "
                "JSON peak-motion content.")

        # Store the original file-like response for the existing parser API.
        self.set_original_content(content=data)
        try:
            if isinstance(data, (str, bytes, bytearray)):
                json_data = json.loads(data)
            else:
                json_data = json.load(data)
        except (json.JSONDecodeError, UnicodeDecodeError, TypeError,
                AttributeError) as error:
            raise ValueError(
                "RRSM Peak Motion response is invalid: expected JSON "
                "peak-motion content; malformed JSON ({}).".format(error)
            ) from error

        if isinstance(json_data, list):
            json_data = {'event-list': json_data}
        elif not isinstance(json_data, dict):
            raise ValueError(
                "RRSM Peak Motion response is invalid: expected a top-level "
                "list or an object containing an 'event-list' list.")

        if 'event-list' not in json_data:
            raise ValueError(
                "RRSM Peak Motion response is invalid: expected top-level "
                "field 'event-list'.")

        event_list = json_data['event-list']
        if not isinstance(event_list, list):
            raise ValueError(
                "RRSM Peak Motion response is invalid: expected field "
                "'event-list' to be a list.")
        if not event_list:
            raise ValueError(
                "RRSM Peak Motion response is invalid: expected a non-empty "
                "'event-list' collection.")

        # Validate every provider record before constructing models. Event
        # values repeat for each station, but all records must still contain
        # the established fields that this provider hierarchy represents.
        for event_index, event_dict in enumerate(event_list):
            structure = "event/station record {}".format(event_index)
            self._require_fields(
                event_dict, self.EVENT_KEYS, structure)
            self._require_fields(
                event_dict, self.STATION_KEYS, structure)

            if 'sensor-channels' not in event_dict:
                raise ValueError(
                    "RRSM Peak Motion response is invalid: expected {} "
                    "field 'sensor-channels'.".format(structure))
            channel_list = event_dict['sensor-channels']
            if not isinstance(channel_list, list):
                raise ValueError(
                    "RRSM Peak Motion response is invalid: expected {} "
                    "field 'sensor-channels' to be a list.".format(structure))

            for channel_index, channel_dict in enumerate(channel_list):
                self._require_fields(
                    channel_dict,
                    self.CHANNEL_KEYS,
                    "{} sensor-channels record {}".format(
                        structure, channel_index),
                )

        # Preserve the provider-specific combined hierarchy without numeric,
        # unit, or cross-record normalization.
        data_item = PeakMotionData()
        data_item.set_data(json_data)

        event_item = PeakMotionEventData()
        for key in self.EVENT_KEYS:
            event_item.set(
                key, event_list[0][key], add_if_not_exist=True)
        data_item.set_event_data(event_item)

        for event_dict in event_list:
            station_data = PeakMotionStationData()
            for key in self.STATION_KEYS:
                station_data.set(
                    key, event_dict[key], add_if_not_exist=True)
            data_item.add_station(station_data)

            for channel_dict in event_dict['sensor-channels']:
                channel_data = PeakMotionChannelData()
                for key in self.CHANNEL_KEYS:
                    channel_data.set(
                        key, channel_dict[key], add_if_not_exist=True)
                station_data.add_channel(channel_data)

        return data_item
