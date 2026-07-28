# -*- coding: utf-8 -*- 
"""
Scientific data models shared by ESM, RRSM, and USGS ComCat ShakeMap content.

Each provider fills the fields it supplies, so provider-specific metadata is
optional. ComCat station collections can contain both instrumented seismic
stations and macroseismic intensity records; macroseismic stations may have no
components. Component units, flags, and uncertainties remain provider-native
rather than being normalized across services.

Provider-specific getters expose optional fields; another provider is not
required to manufacture data it does not supply. A getter returns ``None``
when its field is absent, while an explicit provider empty string remains
``""``.
"""

from paramws.clients.services.basedatastructure import BaseDataStructure

class ShakeMapComponentNode(BaseDataStructure):
    """
    Component-level channel and amplitude data shared across providers.

    Provider-specific fields such as units and uncertainty are optional and
    retain their native representation. This class is part of the
    ShakeMapStationAmplitudes hierarchy. Their getters return ``None`` when
    absent and preserve an explicit provider empty string.
    """
    def __init__(self, data_dict=None, **kwargs):
        super().__init__(data_dict=data_dict, kwargs=kwargs)

    def get_component_name(self):
        """ Return the channel name. """
        return self.get('name')
    
    def get_component_depth(self):
        """ Return the depth. """
        return self.get('depth')
    
    def get_acceleration(self):
        """ Return the acceleration. """
        return self.get('acc')
    
    def get_acceleration_flag(self):
        """ Return the acceleration flag. """
        return self.get('accflag')

    def get_acceleration_units(self):
        """
        Return ``units`` from the USGS ComCat channel ``amplitudes[]`` entry
        with ``name="pga"``, the native acceleration units, or ``None`` when
        absent.
        """
        return self.get('accunits')

    def get_acceleration_uncertainty(self):
        """
        Return ``ln_sigma`` from the USGS ComCat channel ``amplitudes[]``
        entry with ``name="pga"``, or ``None`` when absent. This is the
        logarithmic measurement uncertainty.
        """
        return self.get('accln_sigma')
    
    def get_velocity(self):
        """ Return the velocity. """
        return self.get('vel')
    
    def get_velocity_flag(self):
        """ Return the velocity flag. """
        return self.get('velflag')

    def get_velocity_units(self):
        """
        Return ``units`` from the USGS ComCat channel ``amplitudes[]`` entry
        with ``name="pgv"``, the native velocity units, or ``None`` when
        absent.
        """
        return self.get('velunits')

    def get_velocity_uncertainty(self):
        """
        Return ``ln_sigma`` from the USGS ComCat channel ``amplitudes[]``
        entry with ``name="pgv"``, or ``None`` when absent. This is the
        logarithmic measurement uncertainty.
        """
        return self.get('velln_sigma')
    
    def get_psa03(self):
        """ Return the PSA03. """
        return self.get('psa03')
    
    def get_psa03_flag(self):
        """ Return the PSA03 flag. """
        return self.get('psa03flag')

    def get_psa03_units(self):
        """
        Return ``units`` from the USGS ComCat channel ``amplitudes[]`` entry
        with ``name="sa(0.3)"``, the native spectral-acceleration units, or
        ``None`` when absent.
        """
        return self.get('psa03units')

    def get_psa03_uncertainty(self):
        """
        Return ``ln_sigma`` from the USGS ComCat channel ``amplitudes[]``
        entry with ``name="sa(0.3)"``, or ``None`` when absent. This is the
        logarithmic measurement uncertainty.
        """
        return self.get('psa03ln_sigma')
    
    def get_psa10(self):
        """ Return the PSA10. """
        return self.get('psa10')
    
    def get_psa10_flag(self):
        """ Return the PSA10 flag. """
        return self.get('psa10flag')

    def get_psa10_units(self):
        """
        Return ``units`` from the USGS ComCat channel ``amplitudes[]`` entry
        with ``name="sa(1.0)"``, the native spectral-acceleration units, or
        ``None`` when absent.
        """
        return self.get('psa10units')

    def get_psa10_uncertainty(self):
        """
        Return ``ln_sigma`` from the USGS ComCat channel ``amplitudes[]``
        entry with ``name="sa(1.0)"``, or ``None`` when absent. This is the
        logarithmic measurement uncertainty.
        """
        return self.get('psa10ln_sigma')
    
    def get_psa30(self):
        """ Return the PSA30. """
        return self.get('psa30')
    
    def get_psa30_flag(self):
        """ Return the PSA30 flag. """
        return self.get('psa30flag')

    def get_psa30_units(self):
        """
        Return ``units`` from the USGS ComCat channel ``amplitudes[]`` entry
        with ``name="sa(3.0)"``, the native spectral-acceleration units, or
        ``None`` when absent.
        """
        return self.get('psa30units')

    def get_psa30_uncertainty(self):
        """
        Return ``ln_sigma`` from the USGS ComCat channel ``amplitudes[]``
        entry with ``name="sa(3.0)"``, or ``None`` when absent. This is the
        logarithmic measurement uncertainty.
        """
        return self.get('psa30ln_sigma')


class ShakeMapStationNode(BaseDataStructure):
    """
    Station-level data shared by ESM, RRSM, and USGS ComCat.

    A station retains its provider metadata and a list of components. ComCat
    records explicitly distinguish seismic and macroseismic station types;
    macroseismic stations can validly have an empty component list. Optional
    USGS getters return ``None`` when absent and preserve an explicit empty
    string.
    """
    def __init__(self, data_dict=None, **kwargs):
        super().__init__(data_dict=data_dict, kwargs=kwargs)

    def get_components(self):
        """ 
        Return a List instance of components, i.e. channels. Each item 
        in the list is a again dictionary.
        """
        return self.get('components')

    def get_station_id(self):
        """ Return the station id, which is {netid}.{station code} """
        return self.get('id')
    
    def get_network_code(self):
        """ Return the network id/code. """
        return self.get('netid')
    
    def get_station_code(self):
        """ Return the network code. """
        return self.get('code')
    
    def get_station_name(self):
        """ Return the station name. This is usually the same
        as the station code but may vary depending on the network."""
        return self.get('name')
    
    def get_latitude(self):
        """ Return the station latitude. """
        return self.get('lat')
    
    def get_longitude(self):
        """ Return the station longitude. """
        return self.get('lon')
    
    def get_installation_type(self):
        """ Return the installation type. """
        return self.get('insttype')

    def get_geometry(self):
        """
        Return the USGS ComCat ShakeMap station GeoJSON Feature ``geometry``,
        which preserves its complete location, or ``None`` when absent.
        """
        return self.get('geometry')

    def get_station_type(self):
        """
        Return USGS ComCat station property ``station_type``, which identifies
        a seismic or macroseismic record, or ``None`` when absent.
        """
        return self.get('station_type')

    def get_intensity(self):
        """
        Return USGS ComCat station property ``intensity``, the station's
        reported intensity, or ``None`` when absent.
        """
        return self.get('intensity')

    def get_intensity_uncertainty(self):
        """
        Return the model alias for USGS ``intensity_stddev``, the station
        intensity uncertainty, or ``None`` when absent.

        The original USGS field remains available in the model.
        """
        return self.get('intensity_uncertainty')

    def get_response_count(self):
        """
        Return USGS ComCat station property ``nresp``, the number of responses
        represented by the station, or ``None`` when absent.
        """
        return self.get('nresp')

    def get_distance(self):
        """
        Return USGS ComCat station property ``distance``, the provider's
        station distance, or ``None`` when absent.
        """
        return self.get('distance')
    
class ShakeMapStationAmplitudes(BaseDataStructure):
    """
    Shared collection of ShakeMap seismic and macroseismic station records.

    ESM and RRSM normally supply instrument amplitudes, while a ComCat
    station-list collection may also include macroseismic intensity records.
    Provider-specific collection metadata remains optional.
    """
    def __init__(self, data_dict=None, **kwargs):
        super().__init__(data_dict=data_dict, kwargs=kwargs)

    def get_creation_time(self):
        """ Return the creation time of the data."""
        return self.get('created')
    
    def get_stations(self):
        """ Return the list of stations. Each item in 
        the list is a dictionary. """
        return self.get('stations')

    def get_station_codes(self):
        """ Return the list of station codes. Each item in 
        the list is a string. """
        return [_sta.get_station_code() for _sta in self.get_stations()]
    
class ShakeMapEventData(BaseDataStructure):
    """
    Event data shared by ESM, RRSM, and USGS ComCat.

    The common event fields are available through explicit getters, while
    optional provider-specific metadata such as ComCat status, contributor
    information, geometry, and products remains in the same model. Optional
    USGS getters return ``None`` when absent and preserve an explicit empty
    string.
    """
    def __init__(self, data_dict=None, **kwargs):
        super().__init__(data_dict=data_dict, kwargs=kwargs)
        
    def get_creation_time(self):
        """ Return the creation time of the data."""
        return self.get('created')
    
    def get_event_id(self):
        """ Return the event id. """
        return self.get('id')
    
    def get_catalog(self):
        """ Return the catalog. """
        return self.get('catalog')
    
    def get_latitude(self):
        """ Return the event latitude. """
        return self.get('lat')
    
    def get_longitude(self):
        """ Return the event longitude. """
        return self.get('lon')
    
    def get_magnitude(self):
        """ Return the event magnitude. """
        return self.get('mag')
    
    def get_depth(self):
        """ Return the event depth. """
        return self.get('depth')
    
    def get_origin_time(self):
        """ Return the origin time. """
        return self.get('time') 
    
    def get_time_zone(self):
        """ Return the time zone. """
        return self.get('timezone')
    
    def get_network_code(self):
        """ Return the network id/code. """
        return self.get('netid')
    
    def get_network_desc(self):
        """ Return the network description. """
        return self.get('network')
    
    def get_loc_string(self):
        """ Return the location string. """
        return self.get('locstring')

    def get_geometry(self):
        """
        Return the detailed USGS ComCat GeoJSON Feature ``geometry``, the complete
        event hypocentre point, or ``None`` when absent.
        """
        return self.get('geometry')

    def get_place(self):
        """
        Return USGS ComCat event property ``place``, the provider's event location
        description, or ``None`` when absent.
        """
        return self.get('place')

    def get_status(self):
        """
        Return USGS ComCat event property ``status``, the event review status, or
        ``None`` when absent.
        """
        return self.get('status')

    def get_contributor_network(self):
        """
        Return USGS ComCat event property ``net``, the network contributing the
        preferred event, or ``None`` when absent.
        """
        return self.get('net')

    def get_contributor_code(self):
        """
        Return USGS ComCat event property ``code``, the contributor's native event
        code, or ``None`` when absent.
        """
        return self.get('code')

    def get_contributor_sources(self):
        """
        Return USGS ComCat event property ``sources``, the provider-native source
        list string, or ``None`` when absent.
        """
        return self.get('sources')

    def get_product_index(self):
        """
        Return USGS ComCat event property ``products``, the complete product index,
        or ``None`` when absent.
        """
        return self.get('products')
