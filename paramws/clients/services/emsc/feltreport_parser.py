# -*- coding utf-8 -*-
import io
import os
import zipfile
import json
import urllib
try:
    from paramws.clients.services.baseparser import BaseParser
    from paramws.clients.services.feltreport_data import FeltReportEventData, FeltReportIntensityData
except ImportError:
    from ..baseparser import BaseParser
    from ..feltreport_data import FeltReportEventData, FeltReportIntensityData

class EMSCFeltReportParser(BaseParser):
    """
    Parser class for the EMSC felt report web service output. It handles two
    different types of parsing when the testimonies are requested (intensity)
    and when the testimonies are not requested (basic earthquake location parameters).
    """
    def __init__(self):
        super().__init__()

    @staticmethod
    def _to_float(s):
        if s is None:
            return None
        t = s.strip()
        if t in ("", "NaN", "nan", "NaT", "NaT UTC", "None", "null"):
            return None
        try:
            return float(t)
        except ValueError:
            return None

    def validate(self, data):
        """Check the content of the data."""
        return True
    
    def _validate_zip_file(self, data):
        """
        Check if "data" is a proper zip file content.
        If not, open it as a zip file.
        """
        # Return if "data" is already a zip file
        if isinstance(data, zipfile.ZipFile):
            return data
        
        else:
            try:
                # Check if "data" is a zip file content
                if zipfile.is_zipfile(data):
                    # Yes. Return the zip file
                    return zipfile.ZipFile(data, 'r')
                
                elif isinstance(data, urllib.request.http.client.HTTPResponse):
                    # No. Open it as a zip file
                    return zipfile.ZipFile(io.BytesIO(data.read()), 'r')
                
            except zipfile.BadZipFile:
                return None
                        
    def _parse_intensities(self, file_in_zip, zip_archive):
        if not file_in_zip:
            return None
        
        # Read the csv file, add it to the data structure
        # as the file name being the field name.
        with zip_archive.open(file_in_zip) as _csv_file:
            # Read the file content
            _csv_content = _csv_file.read()
            
            # Make sure file is not empty
            if not _csv_content:
                return None
            
            # Convert the content to a string                        
            try:
                _csv_content = _csv_content.decode("utf-8")
            except UnicodeDecodeError:
                _csv_content = _csv_content.decode("latin-1")
            
            # Split the content into lines
            _csv_lines = _csv_content.splitlines()
            
            # The first four lines are comments, where the first
            # line is the event ID. These will be stored as "comments".
            # The rest of the file is actual intensity data.
            _comments = _csv_lines[0:4]
            _csv_lines = _csv_lines[4:]
            
            # The first line: event ID
            _event_id = _comments[0].replace('#', '')
            
            # Store the rest in a string appended one after another
            # Leave the sharp sign in the beginning of each line.
            _comment_string = ""
            for _comment in _comments[1:]:
                _comment_string += _comment + ' '

            # The rest of the lines are the data. Split them into fields.
            _csv_lines = [_line.split(',') for _line in _csv_lines]
            
            # The first two fields are longitude and latitude.
            # The third field is the raw intensity, and the fourth
            # field is the corrected intensity.
            _intensities = []
            for _line in _csv_lines:
                # Skip empty lines
                if not _line or (len(_line) == 1 and not _line[0].strip()):
                    continue
                parts = [p.strip() for p in _line]
                if len(parts) < 4:
                    continue
                lon = self._to_float(parts[0])
                lat = self._to_float(parts[1])
                raw = self._to_float(parts[2])
                corr = self._to_float(parts[3])
                if lon is None or lat is None:
                    continue
                _intensities.append({"lon": lon, "lat": lat, "raw": raw, "corrected": corr})
            
            return {_event_id: {'unid': _event_id,
                                'intensities': _intensities, 
                                'comments': _comment_string}}

    def parse_testimonies(self, data)->FeltReportIntensityData:
        """
        "data" is a zip file containing the intensity data in comma-seperated
        txt format. There might be more than one files, with file names 
        being the unids of the queried events. The files have a header 
        block with comment lines, then includes four columns for longitude, 
        latitude, raw intensity and corrected intensity. e.g.:
            #20201230_0000049
            #thumbnails 1.0
            #Correction from Bossu et al. 2016
            #longitude,latitude,iraw,icorr
            4.4824,46.0752,1,1
            15.6218,45.7535,1,1
            16.2674,46.2556,1,1
            14.492,46.187,1,1
        Open the zip file, and parse the csv file.
        """
        # Check the zip file. If needed, open it.
        zip_file = self._validate_zip_file(data)
        
        if zip_file is None:
            # Failed. Something is wrong with the data.
            return None
            
        else:
            # Create the data structure to store the intensity data
            intensities = FeltReportIntensityData()

            # The zip file contains text files for intensities.
            # In case there are more than files included, loop
            # through them. Normally, there should be only one file
            # because the web service is queried for a single event.
            _files = zip_file.namelist()

            for _file in _files:
                # Read the csv file, add it to the data structure
                # as the file name being the field name.
                _intensity_data = self._parse_intensities(
                    file_in_zip=_file, zip_archive=zip_file)
                
                # Add the intensity data to the data structure.
                # Each intensity data is a dictionary with a single key
                # (the event ID) and a dictionary as the value.
                # The dictionary contains the again event ID, the comments,
                # and the intensity data.
                # e.g.:
                # {_event_id: 
                #    {'unid': _event_id,
                #     'intensities': intensity info, 4 columns (lon, lat, raw, corrected)
                #     'comments': _comment_string
                #    }
                # }
                intensities.add_field(
                    list(_intensity_data.keys())[0], 
                    list(_intensity_data.values())[0])
            
            return intensities
            
    def parse(self, data)->FeltReportEventData:
        """
        Parse the data returned by the EMSC felt report web service.
        with tetimonies (intensity). The data is in csv format.
        """
        if data and self.validate(data):
            # Store the original content for possible future use
            self.set_original_content(content=data)

            # Read and decode the HTTPResponse body; tolerate non-UTF-8 payloads
            _raw = data.read()
            try:
                _text = _raw.decode('utf-8')
            except UnicodeDecodeError:
                _text = _raw.decode('latin-1')

            # EMSC sometimes returns a list with a single dict, and sometimes a dict
            parsed = json.loads(_text)
            if isinstance(parsed, list):
                if not parsed:
                    return None
                parsed = parsed[0]
            elif not isinstance(parsed, dict):
                # Unexpected shape
                return None

            # Now create the data structure
            return FeltReportEventData(data_dict=parsed)
        
        # Failed. Something is wrong with the data.
        return None