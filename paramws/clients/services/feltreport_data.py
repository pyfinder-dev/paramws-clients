# -*- coding: utf-8 -*- 
from paramws.clients.services.basedatastructure import BaseDataStructure

class FeltReportIntensityData(BaseDataStructure):
    """ Data structure for feltreport intensities """
    def __init__(self, data_dict=None, **kwargs):
        super().__init__(data_dict=data_dict, kwargs=kwargs)

    def get_event_id(self):
        """ Return the event id. """
        return self.get('unid')
    
    def get_intensities(self):
        """ Return the intensities. """
        return self.get('intensities')
    
    def get_comments(self):
        """ Return the comments. """
        return self.get('comments')
    

class FeltReportEventData(BaseDataStructure):
    """ Data structure for feltreport event information"""
    def __init__(self, data_dict=None, **kwargs):
        super().__init__(data_dict=data_dict, kwargs=kwargs)

    def _get_primary_or_fallback(self, primary_field, fallback_path):
        # Provider values such as zero are meaningful, so only None selects
        # the explicitly indexed GeoJSON fallback.
        primary_value = self.get(primary_field)
        if primary_value is not None:
            return primary_value
        return self.get(fallback_path)
        
    def get_event_deltatime(self):
        """ Return the event delta time. """
        return self._get_primary_or_fallback(
            'ev_deltatime', 'features[0].properties.time')
    
    def get_longitude(self):
        """ Return the event longitude. """
        return self._get_primary_or_fallback(
            'ev_longitude', 'features[0].properties.lon')

    def get_latitude(self):
        """ Return the event latitude. """
        return self._get_primary_or_fallback(
            'ev_latitude', 'features[0].properties.lat')

    def get_event_time(self):
        """ Return the event time. """
        return self._get_primary_or_fallback(
            'ev_event_time', 'features[0].properties.time')

    def get_magnitude(self):
        """ Return the event magnitude value. """
        return self._get_primary_or_fallback(
            'ev_mag_value', 'features[0].properties.mag')

    def get_magnitude_type(self):
        """ Return the event magnitude type. """
        return self._get_primary_or_fallback(
            'ev_mag_type', 'features[0].properties.magtype')

    def get_depth(self):
        """ Return the event depth. """
        return self._get_primary_or_fallback(
            'ev_depth', 'features[0].properties.depth')

    def get_event_region(self):
        """ Return the event region. """
        return self._get_primary_or_fallback(
            'ev_region', 'features[0].properties.region')

    def get_event_last_update(self):
        """ Return the event last update. """
        return self._get_primary_or_fallback(
            'ev_last_update', 'features[0].properties.last_update')

    def get_event_nbtestimonies(self):
        """ Return the event number of testimonies. """
        return self._get_primary_or_fallback(
            'ev_nbtestimonies',
            'features[0].properties.feltreportCount',
        )

    def get_event_unid(self):
        """ Return the event unid. """
        return self._get_primary_or_fallback(
            'ev_unid', 'features[0].properties.eventid')

    def get_event_evid(self):
        """ Return the event evid. """
        return self._get_primary_or_fallback(
            'ev_evid', 'features[0].properties.eventid')

    def get_event_id(self):
        """ Return the event id. """
        return self._get_primary_or_fallback(
            'ev_id', 'features[0].properties.eventid')

    def get_full_count(self):
        """ Return the full count. """
        return self._get_primary_or_fallback(
            'full_count', 'features[0].properties.feltreportCount')
