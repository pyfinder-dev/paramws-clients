# -*-coding: utf-8 -*-
from abc import ABC, abstractmethod
from paramws.clients.services import BaseWebServiceConnector

class MissingRequiredOption(ValueError):
    """ 
    Exception for missing required options. 
    """
    pass

class BaseClient(ABC):
    """ 
    Base class for the other classes that encapsulate the actual 
    web service clients. The purpose of this class is to provide a
    single interface to the web services. The client classes are
    defined in the clients/services directory.
    """
    def __init__(self):
        # Concrete clients replace these values with their provider defaults.
        # Keeping configuration on the client prevents connector recreation
        # from silently restoring stale constructor values.
        self.agency = None
        self.base_url = None
        self.end_point = None
        self.version = None

        # The active connector, when the concrete client has created one.
        self.ws_client:BaseWebServiceConnector = None

        # Results describe only the current event-scoped query.
        self.event_data = None
        self.datasets = {}

    def _reset_query_state(self, requested_dataset_keys):
        """
        Prepare fresh result state for one event-scoped query.

        Requested keys are initialized before transport so caller intent
        remains visible even when a requested dataset cannot be populated.
        """
        self.event_data = None
        self.datasets = {
            dataset_key: None
            for dataset_key in requested_dataset_keys
        }
        if self.ws_client is not None:
            self.ws_client.set_data(None)

    @abstractmethod
    def create_web_service(self):
        """ 
        Create a web service client. Should be implemented by the
        child classes.
        """
        return None

    @abstractmethod    
    def query(self, **options):
        """ Query the web service. """
        pass

    def set_agency(self, agency):
        """ Set the agency for the web service. """
        self.agency = agency
        if self.ws_client is not None:
            self.ws_client.set_agency(agency)

    def set_version(self, version):
        """ Set the version for the web service. """
        self.version = version
        if self.ws_client is not None:
            self.ws_client.set_version(version)

    def set_end_point(self, end_point):
        """ Set the service end point for the web service. """
        self.end_point = end_point
        if self.ws_client is not None:
            self.ws_client.set_end_point(end_point)

    def set_base_url(self, base_url):
        """ Set the base url for the web service. """
        if base_url and not base_url.endswith("/"):
            base_url += "/"
        self.base_url = base_url
        if self.ws_client is not None:
            self.ws_client.set_base_url(base_url)

    def set_event_data(self, event_data):
        """ Set the event information. """
        self.event_data = event_data

    def get_web_service(self):
        """ Get the web service client. """
        return self.ws_client
    
    def get_url(self):
        """ Return the combined URL (base + options) for the web service. """
        return self.ws_client.get_combined_url()
    
    def get_agency(self):
        """ Get the agency for the web service. """
        return self.agency
    
    def get_version(self):
        """ Get the version for the web service. """
        return self.version
    
    def get_end_point(self):
        """ Get the end point for the web service. """
        return self.end_point
    
    def get_base_url(self):
        """ Get the base url for the web service. """
        return self.base_url
        
    def get_event_data(self):
        """ Return the event information. """
        return self.event_data

    def get_datasets(self):
        """ Return the datasets for the current query. """
        return self.datasets
