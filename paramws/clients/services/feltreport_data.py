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
        
    def get_event_deltatime(self):
        """ Return the event delta time. """
        print(self.get_data())
        print(self.get('features'))
        print(self.get('features[0]'))
        print(self.get('features[0].time'))
        return self.get('ev_deltatime') or self.get('features[0].properties.time')
    
    def get_longitude(self):
        """ Return the event longitude. """
        return self.get('ev_longitude') or self.get('features[0].properties.lon')

    def get_latitude(self):
        """ Return the event latitude. """
        return self.get('ev_latitude') or self.get('features[0].properties.lat')

    def get_event_time(self):
        """ Return the event time. """
        return self.get('ev_event_time') or self.get('features[0].properties.time')

    def get_magnitude(self):
        """ Return the event magnitude value. """
        return self.get('ev_mag_value') or self.get('features[0].properties.mag')

    def get_magnitude_type(self):
        """ Return the event magnitude type. """
        return self.get('ev_mag_type') or self.get('features[0].properties.magtype')

    def get_depth(self):
        """ Return the event depth. """
        return self.get('ev_depth') or self.get('features[0].properties.depth')

    def get_event_region(self):
        """ Return the event region. """
        return self.get('ev_region') or self.get('features[0].properties.region')

    def get_event_last_update(self):
        """ Return the event last update. """
        return self.get('ev_last_update') or self.get('features[0].properties.last_update')

    def get_event_nbtestimonies(self):
        """ Return the event number of testimonies. """
        return self.get('ev_nbtestimonies') or self.get('features[0].properties.feltreportCount')

    def get_event_unid(self):
        """ Return the event unid. """
        return self.get('ev_unid') or self.get('features[0].properties.eventid')

    def get_event_evid(self):
        """ Return the event evid. """
        return self.get('ev_evid') or self.get('features[0].properties.eventid')

    def get_event_id(self):
        """ Return the event id. """
        return self.get('ev_id') or self.get('features[0].properties.eventid')

    def get_full_count(self):
        """ Return the full count. """
        return self.get('full_count') or self.get('features[0].properties.feltreportCount')
