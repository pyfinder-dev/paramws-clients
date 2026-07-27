# -*- coding: utf-8 -*-
import csv
import io
import json
import os
import zipfile

from paramws.clients.services.baseparser import BaseParser
from paramws.clients.services.feltreport_data import (
    FeltReportEventData,
    FeltReportIntensityData,
)


class EMSCFeltReportParser(BaseParser):
    """
    Parse the two response representations returned by EMSC felt reports.

    Testimony responses are ZIP archives containing provider CSV/text files.
    Event responses are JSON and may be either one event dictionary or a
    non-empty list whose first event retains the service's established
    single-event selection behavior.
    """

    _MISSING_NUMERIC_VALUES = {
        "",
        "NaN",
        "nan",
        "NaT",
        "NaT UTC",
        "None",
        "null",
    }
    _INTENSITY_HEADER = ("longitude", "latitude", "iraw", "icorr")

    def __init__(self):
        super().__init__()

    @classmethod
    def _to_float(cls, value, field_name, row_number):
        """
        Convert a provider numeric field without replacing malformed text.

        EMSC's known missing-value markers remain absence. Other text is a
        schema failure rather than a reason to silently discard a row.
        """
        if value is None:
            return None

        text = value.strip()
        if text in cls._MISSING_NUMERIC_VALUES:
            return None
        try:
            return float(text)
        except (TypeError, ValueError) as error:
            raise ValueError(
                "EMSC felt-intensity CSV row {} has malformed {} value {!r}."
                .format(row_number, field_name, value)
            ) from error

    def validate(self, data):
        """Return whether parser input exists; detailed checks happen locally."""
        return data is not None

    @staticmethod
    def _zip_error(detail):
        return ValueError(
            "EMSC felt-intensity ZIP content is invalid: {}.".format(detail)
        )

    def _open_zip_file(self, data):
        """
        Return ``(archive, opened_here)`` for established ZIP input forms.

        Existing ``ZipFile`` instances remain caller-owned. ZIP wrappers
        created for paths, bytes, or file-like response bodies are closed by
        parse_testimonies(), while the supplied file-like object itself is
        never closed.
        """
        if isinstance(data, zipfile.ZipFile):
            return data, False

        try:
            if isinstance(data, (bytes, bytearray, memoryview)):
                archive = zipfile.ZipFile(io.BytesIO(bytes(data)), "r")
            elif isinstance(data, (str, os.PathLike)):
                archive = zipfile.ZipFile(data, "r")
            elif hasattr(data, "read"):
                seekable = False
                if hasattr(data, "seekable"):
                    try:
                        seekable = data.seekable()
                    except (OSError, ValueError):
                        seekable = False

                if seekable:
                    archive = zipfile.ZipFile(data, "r")
                else:
                    payload = data.read()
                    if not isinstance(
                            payload, (bytes, bytearray, memoryview)):
                        raise self._zip_error(
                            "the response body is not binary")
                    archive = zipfile.ZipFile(
                        io.BytesIO(bytes(payload)), "r")
            else:
                raise self._zip_error(
                    "the supplied value is not a ZIP archive or binary input")
        except ValueError as error:
            if str(error).startswith("EMSC felt-intensity ZIP content"):
                raise
            raise self._zip_error(str(error)) from error
        except (OSError, TypeError, zipfile.BadZipFile,
                zipfile.LargeZipFile) as error:
            raise self._zip_error(str(error)) from error

        return archive, True

    @staticmethod
    def _decode_intensity_content(content, filename):
        if not content:
            raise ValueError(
                "EMSC felt-intensity file {!r} is empty.".format(filename)
            )

        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            text = content.decode("latin-1")
        if not text.strip():
            raise ValueError(
                "EMSC felt-intensity file {!r} is empty.".format(filename)
            )
        return text

    def _parse_intensities(self, file_in_zip, zip_archive):
        """
        Parse one provider intensity file with the standard CSV reader.

        The first line identifies the event, the next two are provider
        comments, and the fourth declares the four scientific columns.
        """
        try:
            with zip_archive.open(file_in_zip) as csv_file:
                csv_content = csv_file.read()
        except (OSError, RuntimeError, ValueError,
                zipfile.BadZipFile) as error:
            raise self._zip_error(
                "could not read {!r}: {}".format(file_in_zip, error)
            ) from error

        text = self._decode_intensity_content(
            csv_content, file_in_zip)
        try:
            rows = list(csv.reader(io.StringIO(text), strict=True))
        except csv.Error as error:
            raise ValueError(
                "EMSC felt-intensity CSV {!r} is malformed: {}."
                .format(file_in_zip, error)
            ) from error

        if len(rows) < 4:
            raise ValueError(
                "EMSC felt-intensity CSV {!r} is missing its required "
                "event, comment, or header structure.".format(file_in_zip)
            )

        event_row = rows[0]
        if len(event_row) != 1 or not event_row[0].strip().startswith("#"):
            raise ValueError(
                "EMSC felt-intensity CSV {!r} is missing its event "
                "identifier.".format(file_in_zip)
            )
        event_id = event_row[0].strip()[1:].strip()
        if not event_id:
            raise ValueError(
                "EMSC felt-intensity CSV {!r} is missing its event "
                "identifier.".format(file_in_zip)
            )

        # Both provider comment rows must retain the established comment
        # shape. Their text is intentionally not interpreted scientifically.
        for row_number, comment_row in enumerate(rows[1:3], start=2):
            if (not comment_row
                    or not comment_row[0].strip().startswith("#")):
                raise ValueError(
                    "EMSC felt-intensity CSV {!r} has malformed required "
                    "comment row {}.".format(file_in_zip, row_number)
                )

        header = [field.strip().lower() for field in rows[3]]
        if header:
            header[0] = header[0].lstrip("#").strip()
        if tuple(header) != self._INTENSITY_HEADER:
            raise ValueError(
                "EMSC felt-intensity CSV {!r} requires columns "
                "longitude, latitude, iraw, and icorr."
                .format(file_in_zip)
            )

        intensities = []
        for row_number, row in enumerate(rows[4:], start=5):
            if not row or all(not value.strip() for value in row):
                continue
            if len(row) != 4:
                raise ValueError(
                    "EMSC felt-intensity CSV {!r} row {} must contain "
                    "exactly four columns.".format(file_in_zip, row_number)
                )

            longitude = self._to_float(
                row[0], "longitude", row_number)
            latitude = self._to_float(
                row[1], "latitude", row_number)
            raw_intensity = self._to_float(
                row[2], "raw intensity", row_number)
            corrected_intensity = self._to_float(
                row[3], "corrected intensity", row_number)

            # A row without a location cannot represent a usable intensity
            # point. Known provider missing markers are not malformed input,
            # but an archive containing only such rows is rejected below.
            if longitude is None or latitude is None:
                continue
            intensities.append({
                "lon": longitude,
                "lat": latitude,
                "raw": raw_intensity,
                "corrected": corrected_intensity,
            })

        if not intensities:
            raise ValueError(
                "EMSC felt-intensity CSV {!r} contains no usable data rows."
                .format(file_in_zip)
            )

        source_lines = text.splitlines()
        comment_string = " ".join(source_lines[1:4]) + " "
        return {
            event_id: {
                "unid": event_id,
                "intensities": intensities,
                "comments": comment_string,
            },
        }

    def parse_testimonies(self, data)->FeltReportIntensityData:
        """
        Parse an EMSC ZIP containing one or more intensity CSV/text files.

        Unrelated archive members are ignored. At least one usable ``.txt`` or
        ``.csv`` member is required because those are the provider's
        established intensity representations.
        """
        zip_file, opened_here = self._open_zip_file(data)
        try:
            try:
                members = [
                    member
                    for member in zip_file.infolist()
                    if not member.is_dir()
                ]
            except (OSError, RuntimeError, zipfile.BadZipFile) as error:
                raise self._zip_error(str(error)) from error

            if not members:
                raise self._zip_error("the archive is empty")

            intensity_members = [
                member
                for member in members
                if os.path.splitext(member.filename)[1].lower()
                in {".csv", ".txt"}
            ]
            if not intensity_members:
                raise self._zip_error(
                    "the archive has no CSV/text intensity content")

            intensities = FeltReportIntensityData()
            for member in intensity_members:
                intensity_data = self._parse_intensities(
                    file_in_zip=member,
                    zip_archive=zip_file,
                )
                event_id, event_data = next(iter(intensity_data.items()))
                if event_id in intensities.keys():
                    raise ValueError(
                        "EMSC felt-intensity ZIP contains duplicate event "
                        "identifier {!r}.".format(event_id)
                    )
                intensities.add_field(event_id, event_data)
            return intensities
        finally:
            if opened_here:
                zip_file.close()

    @staticmethod
    def _read_event_content(data):
        if isinstance(data, str):
            return data
        if isinstance(data, (bytes, bytearray, memoryview)):
            raw_content = bytes(data)
        elif hasattr(data, "read"):
            raw_content = data.read()
            if isinstance(raw_content, str):
                return raw_content
        else:
            raise ValueError(
                "EMSC felt-report event JSON input is not text or bytes."
            )

        if not isinstance(raw_content, bytes):
            raise ValueError(
                "EMSC felt-report event JSON input is not text or bytes."
            )
        try:
            return raw_content.decode("utf-8")
        except UnicodeDecodeError:
            return raw_content.decode("latin-1")

    def parse(self, data)->FeltReportEventData:
        """
        Parse EMSC event JSON while retaining its established event model.
        """
        if not self.validate(data):
            raise ValueError("EMSC felt-report event JSON is empty.")

        self.set_original_content(content=data)
        text = self._read_event_content(data)
        if not text.strip():
            raise ValueError("EMSC felt-report event JSON is empty.")

        try:
            parsed = json.loads(text)
        except (TypeError, json.JSONDecodeError) as error:
            raise ValueError(
                "EMSC felt-report event JSON is malformed: {}."
                .format(error)
            ) from error

        if isinstance(parsed, list):
            if not parsed:
                raise ValueError("EMSC felt-report event JSON is empty.")
            parsed = parsed[0]
        elif not isinstance(parsed, dict):
            raise ValueError(
                "EMSC felt-report event JSON has an incompatible top-level "
                "shape; expected a dictionary or non-empty list."
            )

        if not isinstance(parsed, dict):
            raise ValueError(
                "EMSC felt-report event JSON list must contain event "
                "dictionaries."
            )
        if not parsed:
            raise ValueError("EMSC felt-report event JSON is empty.")

        event_data = FeltReportEventData(data_dict=parsed)
        event_identifiers = (
            event_data.get_event_id(),
            event_data.get_event_unid(),
            event_data.get_event_evid(),
        )
        has_event_identifier = any(
            identifier is not None
            and not (
                isinstance(identifier, str)
                and not identifier.strip()
            )
            for identifier in event_identifiers
        )
        if not has_event_identifier:
            raise ValueError(
                "EMSC felt-report event JSON is missing its event "
                "identifier."
            )
        return event_data
