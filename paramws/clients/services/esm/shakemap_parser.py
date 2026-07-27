# -*- coding: utf-8 -*-
import datetime
import xmltodict
from paramws.clients.services.baseparser import BaseParser
from paramws.clients.services.shakemap_data import ShakeMapEventData
from paramws.clients.services.shakemap_data import ShakeMapStationAmplitudes
from paramws.clients.services.shakemap_data import ShakeMapStationNode
from paramws.clients.services.shakemap_data import ShakeMapComponentNode

class ESMShakeMapParser(BaseParser):
    """
    Parser class for the ESM ShakeMap web service output. The return from 
    the web service is an XML file without and style sheet. The parser converts
    the XML file to a dictionary, and then creates a data structure.
    """
    def __init__(self):
        super().__init__()

    @staticmethod
    def _invalid_content(expected_content, detail):
        """Build the provider-specific validation error required by clients."""
        return ValueError(
            "ESM returned invalid successful content; expected {}. {}"
            .format(expected_content, detail)
        )

    def _parse_xml_root(self, data, root_name, expected_content):
        """Return one required ESM XML root as a dictionary."""
        if not data:
            raise self._invalid_content(
                expected_content,
                "The response was empty.",
            )

        try:
            xml_content = xmltodict.parse(data)
        except Exception as error:
            raise self._invalid_content(
                expected_content,
                "The XML is malformed: {}.".format(error),
            ) from error

        root = xml_content.get(root_name)
        if not isinstance(root, dict):
            raise self._invalid_content(
                expected_content,
                "The top-level element must be <{}>.".format(root_name),
            )
        return root

    def _required_number(self, record, key, converter, expected_content):
        """Convert one required provider value and report its field clearly."""
        if key not in record:
            raise self._invalid_content(
                expected_content,
                "Required field {!r} is missing.".format(key),
            )
        try:
            return converter(record[key])
        except (TypeError, ValueError, OverflowError) as error:
            raise self._invalid_content(
                expected_content,
                "Required numeric field {!r} has malformed value {!r}."
                .format(key, record[key]),
            ) from error

    def _parse_component(self, component_xml, expected_content):
        """Create one component while retaining ESM response flags verbatim."""
        if not isinstance(component_xml, dict):
            raise self._invalid_content(
                expected_content,
                "Each <comp> record must contain XML attributes.",
            )

        component_name = component_xml.get('@name')
        if not component_name:
            raise self._invalid_content(
                expected_content,
                "Each <comp> record requires a non-empty @name.",
            )

        component = {'name': component_name}
        depth = component_xml.get('@depth')
        if depth is None:
            component['depth'] = 0.0
        else:
            try:
                component['depth'] = float(depth)
            except (TypeError, ValueError, OverflowError) as error:
                raise self._invalid_content(
                    expected_content,
                    "Component {!r} has malformed numeric @depth {!r}."
                    .format(component_name, depth),
                ) from error

        for key in ('acc', 'vel', 'psa03', 'psa10', 'psa30'):
            measurement = component_xml.get(key)
            if measurement is None:
                component[key] = None
                continue
            if not isinstance(measurement, dict):
                raise self._invalid_content(
                    expected_content,
                    "Component {!r} field {!r} must contain value and flag "
                    "attributes.".format(component_name, key),
                )
            if '@value' not in measurement or '@flag' not in measurement:
                raise self._invalid_content(
                    expected_content,
                    "Component {!r} field {!r} requires @value and @flag."
                    .format(component_name, key),
                )
            try:
                component[key] = float(measurement['@value'])
            except (TypeError, ValueError, OverflowError) as error:
                raise self._invalid_content(
                    expected_content,
                    "Component {!r} field {!r} has malformed numeric value "
                    "{!r}.".format(
                        component_name,
                        key,
                        measurement['@value'],
                    ),
                ) from error

            # ESM defines these flags as provider response values. Their
            # string representation is meaningful and must not be normalized.
            component[key + 'flag'] = measurement['@flag']

        return ShakeMapComponentNode(data_dict=component)

    def _parse_amplitudes(self, data)->ShakeMapStationAmplitudes:
        """
        Parse the data returned by the ESM ShakeMap web service.
        This method converts the XML content to a dictionary only
        for format="event_dat". 
        """
        self.set_original_content(content=data)

        expected_content = "ESM ShakeMap station-amplitude XML"
        station_list = self._parse_xml_root(
            data,
            'stationlist',
            expected_content,
        )

        # Initialize the main data structure for the ESM ShakeMap.
        # The top-level data structure is a dictionary with two keys:
        # - created: The creation time of the data.
        # - stations: A list of stations.
        creation_value = station_list.get('@created')
        if creation_value is None or (
                isinstance(creation_value, str)
                and not creation_value.strip()):
            # RRSM currently sends an empty attribute, while other compatible
            # responses may omit it. Creation time is optional metadata and
            # must not discard otherwise valid station measurements.
            _creation_time = None
        else:
            try:
                _creation_time = datetime.datetime.fromtimestamp(
                    int(creation_value))
            except (TypeError, ValueError, OverflowError, OSError) as error:
                raise self._invalid_content(
                    expected_content,
                    "The provider creation timestamp is invalid: {!r}."
                    .format(creation_value),
                ) from error
        
        _esm_toplevel_data = {"created": _creation_time, "stations": []}
        esm_shakemap_data = ShakeMapStationAmplitudes(_esm_toplevel_data)

        station_records = station_list.get('station')
        if isinstance(station_records, dict):
            station_records = [station_records]
        if not isinstance(station_records, list) or not station_records:
            raise self._invalid_content(
                expected_content,
                "The <stationlist> element requires at least one <station>.",
            )

        for _sta in station_records:
            if not isinstance(_sta, dict):
                raise self._invalid_content(
                    expected_content,
                    "Each <station> record must contain XML attributes.",
                )
            if not _sta.get('@netid') or not _sta.get('@code'):
                raise self._invalid_content(
                    expected_content,
                    "Each <station> requires non-empty @netid and @code.",
                )

            # Station ID is constructed using network and station code
            # to search for the station in station list
            _id = "{}.{}".format(_sta['@netid'], _sta['@code'])

            # Each station is a dictionary of attributes, and contains
            # another list for the components
            my_keys = ['name', 'code', 'netid', 'source', 'insttype', 
                       'lat', 'lon']
            keys_in_xml = ['@name', '@code', '@netid', '@source', 
                           '@insttype', '@lat', '@lon']
            station = {'id': _id, 'components': []}
            for my_key, real_key in zip(my_keys, keys_in_xml):
                try:
                    station[my_key] = _sta[real_key]
                except:
                    station[my_key] = None
            
            # Create a station-level dictionary (in reality, a wrapper 
            # around the dictionary)
            station_node = ShakeMapStationNode(data_dict=station)

            # Add the station node to the main data structure
            esm_shakemap_data.stations.append(station_node)

            # Each component is again a dictionary
            if 'comp' in _sta:
                component_records = _sta['comp']
                if isinstance(component_records, dict):
                    component_records = [component_records]
                if not isinstance(component_records, list) \
                        or not component_records:
                    raise self._invalid_content(
                        expected_content,
                        "A present <comp> collection must contain records.",
                    )

                for _comp in component_records:
                    station_node.components.append(
                        self._parse_component(_comp, expected_content)
                    )

        # Pass the main data structure back to the caller
        return esm_shakemap_data
    
    def parse(self, data)->ShakeMapStationAmplitudes:
        """
        Calls the internal parsing method for format="event_dat" option
        if the data is successfully validated. 
        """
        return self._parse_amplitudes(data)

    def validate(self, data):
        """Check the content of the data."""
        if not data:
            return False
        try:
            xmltodict.parse(data)
        except Exception:
            return False
        return True
    
    def parse_earthquake(self, data)->ShakeMapEventData:
        """ 
        Parse the data returned by the ESM ShakeMap web service 
        when format='event'. Called by the parse_response() method
        of the ESM ShakeMap client.
        """
        expected_content = "ESM ShakeMap event XML"
        self.set_original_content(content=data)
        eq = self._parse_xml_root(data, 'earthquake', expected_content)

        if not eq.get('@id'):
            raise self._invalid_content(
                expected_content,
                "The <earthquake> record requires a non-empty @id.",
            )

        keys = ['id', 'catalog', 'lat', 'lon', 'depth', 'mag', 'year',
                'month', 'day', 'hour', 'minute', 'second', 'timezone',
                'time', 'locstring', 'netid', 'network', 'created']
        float_keys = {'lat', 'lon', 'depth', 'mag', 'second'}
        integer_keys = {'year', 'month', 'day', 'hour', 'minute'}
        event_data = {}

        for key in keys:
            xml_key = '@' + key
            if key in float_keys:
                event_data[key] = self._required_number(
                    eq,
                    xml_key,
                    float,
                    expected_content,
                )
            elif key in integer_keys:
                event_data[key] = self._required_number(
                    eq,
                    xml_key,
                    int,
                    expected_content,
                )
            else:
                event_data[key] = eq.get(xml_key)

        return ShakeMapEventData(event_data)
