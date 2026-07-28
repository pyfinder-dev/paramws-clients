# -*- coding: utf-8 -*-
"""
Parse the contracted scientific content exposed through USGS ComCat.

Detailed event GeoJSON supplies both event information and the product index
used to locate the requested data. Selection follows ComCat's provider-specific
preference rules, then this module parses only the contracted ShakeMap station
list and 1 km DYFI GeoJSON into the project's existing scientific models.

This parser deliberately contains no transport behavior, arbitrary-product
framework, or fallback to other ShakeMap formats or DYFI resolutions. Those
boundaries keep provider discovery separate from requests and prevent alternate
representations from silently changing the scientific dataset.
"""

import copy
import json
import math

from paramws.clients.services.baseparser import BaseParser
from paramws.clients.services.basedatastructure import BaseDataStructure
from paramws.clients.services.feltreport_data import FeltReportIntensityData
from paramws.clients.services.shakemap_data import (
    ShakeMapComponentNode,
    ShakeMapEventData,
    ShakeMapStationAmplitudes,
    ShakeMapStationNode,
)
from paramws.clients.services.usgs.exceptions import (
    DatasetNotAvailableError,
)


class USGSComCatParser(BaseParser):
    """
    Parse the contracted USGS ComCat event and scientific product content.

    ComCat event detail supplies a product index rather than embedding the
    complete ShakeMap and DYFI datasets. Product preference and exact content
    selection therefore live beside the provider-specific parsers, without
    introducing a general product or GeoJSON framework.
    """

    _PRODUCT_CONTENT_PATHS = {
        "shakemap": "download/stationlist.json",
        "dyfi": "dyfi_geo_1km.geojson",
    }
    _AMPLITUDE_FIELDS = {
        "pga": "acc",
        "pgv": "vel",
        "sa(0.3)": "psa03",
        "sa(1.0)": "psa10",
        "sa(3.0)": "psa30",
    }

    @staticmethod
    def _invalid_content(expected_content, detail):
        """Build the provider-specific validation error required by clients."""
        return ValueError(
            "USGS/ComCat returned invalid successful content; expected {}. {}"
            .format(expected_content, detail)
        )

    def _load_json(self, data, expected_content):
        """Load JSON from connector text, bytes, mappings, or response streams."""
        self.set_original_content(content=data)
        content = data
        if hasattr(content, "read"):
            try:
                content = content.read()
            except Exception as error:
                raise self._invalid_content(
                    expected_content,
                    "The response stream could not be read: {}.".format(error),
                ) from error

        if isinstance(content, (dict, list)):
            return copy.deepcopy(content)

        try:
            return json.loads(content)
        except (TypeError, ValueError, UnicodeDecodeError) as error:
            raise self._invalid_content(
                expected_content,
                "The JSON is malformed: {}.".format(error),
            ) from error

    @staticmethod
    def _is_number(value):
        """Return whether a provider value is a finite JSON number."""
        return (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and (not isinstance(value, float) or math.isfinite(value))
        )

    @staticmethod
    def _is_optional_missing_value(value):
        """
        Identify provider missing markers without converting valid zero values.

        USGS station content can use JSON null, an empty string, or the string
        ``"null"`` for optional numeric fields. The original scalar remains in
        the model; this helper only prevents inappropriate numeric conversion.
        """
        if value is None:
            return True
        return (
            isinstance(value, str)
            and value.strip().lower() in ("", "null")
        )

    def _validate_optional_number(self, value, field_name, expected_content):
        """Validate one supplied scientific value while preserving its scalar."""
        if self._is_optional_missing_value(value):
            return value
        if self._is_number(value):
            return value

        # Some USGS optional scientific values appear as numeric text. Validate
        # that representation without converting it, because callers may need
        # the provider-native scalar type as well as its scientific value.
        if isinstance(value, str):
            try:
                numeric_value = float(value)
            except ValueError:
                numeric_value = None
            if numeric_value is not None and math.isfinite(numeric_value):
                return value

        raise self._invalid_content(
            expected_content,
            "Scientific field {!r} has malformed non-empty value {!r}."
            .format(field_name, value),
        )

    def _validate_required_coordinates(
            self, geometry, expected_type, minimum_size, expected_content):
        """Validate required point geometry and return its native coordinates."""
        if not isinstance(geometry, dict):
            raise self._invalid_content(
                expected_content,
                "Required geometry must be a GeoJSON object.",
            )
        if geometry.get("type") != expected_type:
            raise self._invalid_content(
                expected_content,
                "Required geometry type must be {!r}.".format(expected_type),
            )
        coordinates = geometry.get("coordinates")
        if not isinstance(coordinates, list) or len(coordinates) < minimum_size:
            raise self._invalid_content(
                expected_content,
                "Required {} geometry must contain at least {} coordinates."
                .format(expected_type, minimum_size),
            )
        for coordinate in coordinates[:minimum_size]:
            if not self._is_number(coordinate):
                raise self._invalid_content(
                    expected_content,
                    "Required geometry contains malformed coordinate {!r}."
                    .format(coordinate),
                )
        return coordinates

    def parse(self, data):
        """Parse a detailed single-event ComCat GeoJSON feature."""
        return self.parse_event_detail(data)

    def validate(self, data):
        """Return whether data is syntactically valid JSON."""
        try:
            self._load_json(data, "USGS/ComCat JSON")
        except ValueError:
            return False
        return True

    def parse_event_detail(self, data):
        """Parse detailed event GeoJSON into the existing event model."""
        expected_content = "a detailed single-event GeoJSON Feature"
        feature = self._load_json(data, expected_content)
        if not isinstance(feature, dict) or feature.get("type") != "Feature":
            raise self._invalid_content(
                expected_content,
                "The top-level value must be one GeoJSON Feature.",
            )

        event_id = feature.get("id")
        if not isinstance(event_id, str) or not event_id:
            raise self._invalid_content(
                expected_content,
                "The event requires a non-empty string identifier.",
            )

        properties = feature.get("properties")
        if not isinstance(properties, dict):
            raise self._invalid_content(
                expected_content,
                "The event requires a properties object.",
            )

        product_index = properties.get("products")
        if product_index is not None and not isinstance(product_index, dict):
            raise self._invalid_content(
                expected_content,
                "A supplied product index must be an object.",
            )

        coordinates = self._validate_required_coordinates(
            feature.get("geometry"),
            "Point",
            3,
            expected_content,
        )

        # Magnitude and time are optional provider fields, but non-empty values
        # must retain a scientifically usable numeric representation.
        for field_name in ("mag", "time"):
            if field_name in properties:
                self._validate_optional_number(
                    properties[field_name],
                    field_name,
                    expected_content,
                )

        event_data = copy.deepcopy(properties)
        event_data.update({
            "id": event_id,
            "geometry": copy.deepcopy(feature["geometry"]),
            "lon": coordinates[0],
            "lat": coordinates[1],
            "depth": coordinates[2],
        })
        # These aliases let established ShakeMap getters remain meaningful
        # while the original ComCat property names remain available unchanged.
        event_data.setdefault("netid", properties.get("net"))
        event_data.setdefault("locstring", properties.get("place"))
        return ShakeMapEventData(event_data)

    def _product_index(self, event_data):
        """Return a parsed event's optional product index."""
        expected_content = "ComCat preferred-product metadata"
        if isinstance(event_data, BaseDataStructure):
            product_index = event_data.get("products")
        elif isinstance(event_data, dict):
            product_index = event_data.get("products")
        else:
            raise self._invalid_content(
                expected_content,
                "Product selection requires parsed event data.",
            )

        if product_index is None:
            return {}
        if not isinstance(product_index, dict):
            raise self._invalid_content(
                expected_content,
                "The event product index must be an object.",
            )
        return product_index

    def _preferred_product(self, event_data, dataset):
        """Select one product before interpreting its status or contents."""
        expected_content = "ComCat preferred-product metadata"
        if dataset not in self._PRODUCT_CONTENT_PATHS:
            raise ValueError(
                "USGS/ComCat product selection does not support dataset {!r}."
                .format(dataset)
            )

        candidates = self._product_index(event_data).get(dataset)
        if candidates is None or candidates == []:
            raise DatasetNotAvailableError(
                "USGS/ComCat dataset {!r} is not available for this event."
                .format(dataset)
            )
        if not isinstance(candidates, list):
            raise self._invalid_content(
                expected_content,
                "Product candidates for {!r} must be a list.".format(dataset),
            )

        preferred_product = None
        preferred_key = None

        # ComCat defines preference lexicographically: greatest
        # preferredWeight first, with newest updateTime used only when weights
        # tie. Status is deliberately excluded here because DELETE applies
        # only after the preferred contributor/version has been established.
        for index, candidate in enumerate(candidates):
            if not isinstance(candidate, dict):
                raise self._invalid_content(
                    expected_content,
                    "Candidate {} for {!r} must be an object."
                    .format(index, dataset),
                )

            selection_values = []
            for field_name in ("preferredWeight", "updateTime"):
                if field_name not in candidate:
                    raise self._invalid_content(
                        expected_content,
                        "Candidate {} for {!r} is missing required selection "
                        "field {!r}.".format(index, dataset, field_name),
                    )
                value = candidate[field_name]
                if not self._is_number(value):
                    raise self._invalid_content(
                        expected_content,
                        "Candidate {} for {!r} has malformed selection field "
                        "{!r}: {!r}.".format(
                            index,
                            dataset,
                            field_name,
                            value,
                        ),
                    )
                selection_values.append(value)

            candidate_key = tuple(selection_values)
            if preferred_key is None or candidate_key > preferred_key:
                preferred_product = candidate
                preferred_key = candidate_key

        return preferred_product

    def select_product_content(self, event_data, dataset):
        """Return the exact preferred-product content URL unchanged."""
        expected_content = "ComCat preferred-product metadata"
        product = self._preferred_product(event_data, dataset)

        # A DELETE on the selected product means that the provider considers
        # this dataset unavailable. An older or non-preferred product must not
        # be revived as a fallback after this point.
        status = product.get("status")
        if (
                status is not None
                and status != ""
                and not isinstance(status, str)):
            raise self._invalid_content(
                expected_content,
                "Preferred {!r} product status must be a string when supplied."
                .format(dataset),
            )
        if status == "DELETE":
            raise DatasetNotAvailableError(
                "USGS/ComCat dataset {!r} is unavailable because its "
                "preferred product is deleted.".format(dataset)
            )

        # Content selection is intentionally exact. If the contracted path is
        # absent, another resolution or representation would be a different
        # dataset and must not be substituted.
        contents = product.get("contents")
        if contents is None:
            raise DatasetNotAvailableError(
                "USGS/ComCat dataset {!r} lacks required content {!r}."
                .format(dataset, self._PRODUCT_CONTENT_PATHS[dataset])
            )
        if not isinstance(contents, dict):
            raise self._invalid_content(
                expected_content,
                "Preferred {!r} product contents must be an object."
                .format(dataset),
            )

        content_path = self._PRODUCT_CONTENT_PATHS[dataset]
        content_metadata = contents.get(content_path)
        if content_metadata is None:
            raise DatasetNotAvailableError(
                "USGS/ComCat dataset {!r} lacks required content {!r}."
                .format(dataset, content_path)
            )
        if not isinstance(content_metadata, dict):
            raise self._invalid_content(
                expected_content,
                "Content metadata for {!r} must be an object."
                .format(content_path),
            )

        content_url = content_metadata.get("url")
        if content_url is None or content_url == "":
            raise DatasetNotAvailableError(
                "USGS/ComCat dataset {!r} lacks a URL for required content "
                "{!r}.".format(dataset, content_path)
            )
        if not isinstance(content_url, str):
            raise self._invalid_content(
                expected_content,
                "The URL for required content {!r} must be a string."
                .format(content_path),
            )

        # Client transport will consume this provider-discovered URL later.
        # Returning it verbatim avoids rebuilding or otherwise altering it.
        return content_url

    def _parse_component(self, channel, station_id, expected_content):
        """Map one USGS channel into the established component model."""
        if not isinstance(channel, dict):
            raise self._invalid_content(
                expected_content,
                "Each channel for station {!r} must be an object."
                .format(station_id),
            )
        channel_name = channel.get("name")
        if not isinstance(channel_name, str) or not channel_name:
            raise self._invalid_content(
                expected_content,
                "Each channel for station {!r} requires a non-empty name."
                .format(station_id),
            )

        # Keep all provider channel metadata, then remove only the raw
        # amplitude list before translating its supported measurements into
        # the established component fields.
        component = copy.deepcopy(channel)
        amplitudes = component.pop("amplitudes", None)
        if self._is_optional_missing_value(amplitudes):
            amplitudes = []
        if not isinstance(amplitudes, list):
            raise self._invalid_content(
                expected_content,
                "Channel {!r} amplitudes must be a list when supplied."
                .format(channel_name),
            )

        # The mapping is intentionally limited to the five ComCat measurements:
        # pga and pgv use the existing acceleration and velocity fields, while
        # sa(0.3), sa(1.0), and sa(3.0) use their corresponding PSA fields.
        # Unsupported names are not forced into a misleading established field.
        seen_amplitudes = set()
        for amplitude in amplitudes:
            if not isinstance(amplitude, dict):
                raise self._invalid_content(
                    expected_content,
                    "Each amplitude in channel {!r} must be an object."
                    .format(channel_name),
                )
            amplitude_name = amplitude.get("name")
            if not isinstance(amplitude_name, str) or not amplitude_name:
                raise self._invalid_content(
                    expected_content,
                    "Each amplitude in channel {!r} requires a non-empty name."
                    .format(channel_name),
                )
            if amplitude_name not in self._AMPLITUDE_FIELDS:
                continue
            if amplitude_name in seen_amplitudes:
                raise self._invalid_content(
                    expected_content,
                    "Channel {!r} contains duplicate supported amplitude {!r}."
                    .format(channel_name, amplitude_name),
                )
            seen_amplitudes.add(amplitude_name)

            model_field = self._AMPLITUDE_FIELDS[amplitude_name]
            value = amplitude.get("value")
            component[model_field] = self._validate_optional_number(
                value,
                "{}.value".format(amplitude_name),
                expected_content,
            )

            # Units, quality flags, and ln_sigma uncertainty remain exactly as
            # USGS supplied them. In particular, no conversion is made merely
            # to resemble ESM or RRSM component values.
            if "units" in amplitude:
                component[model_field + "units"] = copy.deepcopy(
                    amplitude["units"])
            if "flag" in amplitude:
                component[model_field + "flag"] = copy.deepcopy(
                    amplitude["flag"])
            if "ln_sigma" in amplitude:
                component[model_field + "ln_sigma"] = (
                    self._validate_optional_number(
                        amplitude["ln_sigma"],
                        "{}.ln_sigma".format(amplitude_name),
                        expected_content,
                    )
                )

        return ShakeMapComponentNode(data_dict=component)

    def _parse_station(self, feature, expected_content):
        """Parse one seismic or macroseismic station feature."""
        if not isinstance(feature, dict) or feature.get("type") != "Feature":
            raise self._invalid_content(
                expected_content,
                "Each station record must be a GeoJSON Feature.",
            )
        properties = feature.get("properties")
        if not isinstance(properties, dict):
            raise self._invalid_content(
                expected_content,
                "Each station feature requires a properties object.",
            )

        coordinates = self._validate_required_coordinates(
            feature.get("geometry"),
            "Point",
            2,
            expected_content,
        )
        network = properties.get("network")
        code = properties.get("code")
        station_type = properties.get("station_type")
        for field_name, value in (
                ("network", network),
                ("code", code),
                ("station_type", station_type)):
            if not isinstance(value, str) or not value:
                raise self._invalid_content(
                    expected_content,
                    "Each station requires a non-empty string {!r}."
                    .format(field_name),
                )

        # Some station-list features omit a GeoJSON feature ID. Network and
        # station code still provide the provider's stable station identity.
        station_id = feature.get("id")
        if station_id is None or station_id == "":
            station_id = "{}.{}".format(network, code)
        elif not isinstance(station_id, str):
            raise self._invalid_content(
                expected_content,
                "A supplied station feature identifier must be a string.",
            )

        station = copy.deepcopy(properties)

        # Channels are optional, especially for macroseismic records. Missing
        # and provider null markers therefore become an empty component list,
        # while all other station properties remain available.
        channels = station.pop("channels", None)
        if self._is_optional_missing_value(channels):
            channels = []
        if not isinstance(channels, list):
            raise self._invalid_content(
                expected_content,
                "Station {!r} channels must be a list when supplied."
                .format(station_id),
            )

        for field_name in (
                "intensity",
                "intensity_stddev",
                "intensity_uncertainty",
                "nresp",
                "distance",
                "pga",
                "pgv"):
            if field_name in station:
                self._validate_optional_number(
                    station[field_name],
                    field_name,
                    expected_content,
                )

        # USGS names this field intensity_stddev. Expose the same value through
        # the established uncertainty getter without removing or renaming the
        # original provider field.
        if "intensity_uncertainty" not in station:
            station["intensity_uncertainty"] = station.get(
                "intensity_stddev")

        # Retain the complete GeoJSON geometry and copied provider properties
        # while adding the aliases used by the shared ShakeMap station model.
        station.update({
            "id": station_id,
            "netid": network,
            "lat": coordinates[1],
            "lon": coordinates[0],
            "geometry": copy.deepcopy(feature["geometry"]),
            "components": [],
        })
        station_node = ShakeMapStationNode(data_dict=station)
        for channel in channels:
            station_node.components.append(
                self._parse_component(channel, station_id, expected_content)
            )
        return station_node

    def parse_shakemap_station_list(self, data):
        """Parse the exact ShakeMap station-list JSON product."""
        expected_content = "ShakeMap download/stationlist.json GeoJSON"
        collection = self._load_json(data, expected_content)
        if (
                not isinstance(collection, dict)
                or collection.get("type") != "FeatureCollection"):
            raise self._invalid_content(
                expected_content,
                "The top-level value must be a GeoJSON FeatureCollection.",
            )
        features = collection.get("features")
        if not isinstance(features, list):
            raise self._invalid_content(
                expected_content,
                "The FeatureCollection requires a features list.",
            )

        # Preserve collection-level provider metadata, replacing only the raw
        # GeoJSON features array with the established list of station models.
        top_level = copy.deepcopy(collection)
        top_level.pop("features")
        top_level["stations"] = []
        station_data = ShakeMapStationAmplitudes(data_dict=top_level)
        for feature in features:
            station_data.stations.append(
                self._parse_station(feature, expected_content)
            )
        return station_data

    def _validate_geojson_coordinates(
            self, coordinates, expected_content, path="coordinates"):
        """Validate a non-empty coordinate tree without altering its geometry."""
        if not isinstance(coordinates, list) or not coordinates:
            raise self._invalid_content(
                expected_content,
                "Required geometry {!r} must be a non-empty list.".format(path),
            )
        for index, value in enumerate(coordinates):
            value_path = "{}[{}]".format(path, index)
            if isinstance(value, list):
                self._validate_geojson_coordinates(
                    value,
                    expected_content,
                    value_path,
                )
            elif not self._is_number(value):
                raise self._invalid_content(
                    expected_content,
                    "Required geometry {!r} contains malformed coordinate "
                    "{!r}.".format(value_path, value),
                )

    def _parse_dyfi_feature(self, feature, expected_content):
        """Parse one 1 km DYFI intensity feature without flattening geometry."""
        if not isinstance(feature, dict) or feature.get("type") != "Feature":
            raise self._invalid_content(
                expected_content,
                "Each DYFI intensity record must be a GeoJSON Feature.",
            )
        properties = feature.get("properties")
        if not isinstance(properties, dict):
            raise self._invalid_content(
                expected_content,
                "Each DYFI feature requires a properties object.",
            )
        geometry = feature.get("geometry")
        if not isinstance(geometry, dict):
            raise self._invalid_content(
                expected_content,
                "Each DYFI feature requires a geometry object.",
            )
        geometry_type = geometry.get("type")
        if not isinstance(geometry_type, str) or not geometry_type:
            raise self._invalid_content(
                expected_content,
                "Each DYFI geometry requires a non-empty type.",
            )
        self._validate_geojson_coordinates(
            geometry.get("coordinates"),
            expected_content,
        )

        intensity = copy.deepcopy(properties)
        for field_name in ("cdi", "stddev", "nresp", "dist"):
            if field_name in intensity:
                self._validate_optional_number(
                    intensity[field_name],
                    field_name,
                    expected_content,
                )
        if "name" in intensity and isinstance(
                intensity["name"], (dict, list)):
            raise self._invalid_content(
                expected_content,
                "Optional DYFI field 'name' must be a scalar when supplied.",
            )

        # DYFI geometry stays nested and complete; flattening polygon
        # coordinates would lose its aggregation footprint. The copied
        # properties remain intensity observations, not station amplitudes.
        intensity["geometry"] = copy.deepcopy(geometry)
        intensity["feature_type"] = feature["type"]
        if "id" in feature:
            intensity["id"] = copy.deepcopy(feature["id"])
        return intensity

    def parse_dyfi_1km(self, data):
        """Parse exact 1 km DYFI GeoJSON into felt-intensity data."""
        expected_content = "DYFI dyfi_geo_1km.geojson FeatureCollection"
        collection = self._load_json(data, expected_content)
        if (
                not isinstance(collection, dict)
                or collection.get("type") != "FeatureCollection"):
            raise self._invalid_content(
                expected_content,
                "The top-level value must be a GeoJSON FeatureCollection.",
            )
        features = collection.get("features")
        if not isinstance(features, list):
            raise self._invalid_content(
                expected_content,
                "The FeatureCollection requires a features list.",
            )

        # Keep bbox and any other collection metadata while translating only
        # the feature array into the FeltReportIntensityData record list.
        top_level = copy.deepcopy(collection)
        top_level.pop("features")
        top_level["intensities"] = []
        intensity_data = FeltReportIntensityData(data_dict=top_level)
        for feature in features:
            intensity_data.intensities.append(
                self._parse_dyfi_feature(feature, expected_content)
            )
        return intensity_data
