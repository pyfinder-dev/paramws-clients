# -*- coding: utf-8 -*-
import io
import json
import os
import unittest
import zipfile

from paramws.clients.services.emsc.feltreport_parser import (
    EMSCFeltReportParser,
)
from paramws.clients.services.feltreport_data import (
    FeltReportEventData,
    FeltReportIntensityData,
)


FIXTURE_DIRECTORY = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..",
    "fixtures",
)


def fixture_bytes(filename):
    """Return one deterministic EMSC fixture as bytes."""
    with open(os.path.join(FIXTURE_DIRECTORY, filename), "rb") as fixture:
        return fixture.read()


def intensity_text(event_id="event-one", data_rows=None):
    """Build the established EMSC four-line header and selected rows."""
    if data_rows is None:
        data_rows = ["1,2,3,4"]
    return "\n".join([
        "#" + event_id,
        "#thumbnails 1.0",
        "#Correction from Bossu et al. 2016",
        "#longitude,latitude,iraw,icorr",
    ] + list(data_rows))


def zip_bytes(content=None, filename="event-one.txt"):
    """Return deterministic ZIP bytes containing one selected member."""
    if content is None:
        content = intensity_text()
    if isinstance(content, str):
        content = content.encode("utf-8")

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(filename, content)
    return buffer.getvalue()


def zip_member_bytes(members):
    """Return deterministic ZIP bytes containing the selected named members."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for filename, content in members.items():
            archive.writestr(filename, content)
    return buffer.getvalue()


class TestEMSCFeltReportParser(unittest.TestCase):
    """Test strict EMSC ZIP/CSV and event JSON parsing."""

    def setUp(self):
        self.parser = EMSCFeltReportParser()

    def test_existing_large_zip_fixture_is_retained_and_parsed(self):
        zip_path = os.path.join(
            FIXTURE_DIRECTORY,
            "mt-export-single.zip",
        )

        with zipfile.ZipFile(zip_path) as archive:
            parsed_data = self.parser.parse_testimonies(archive)

        self.assertIsInstance(parsed_data, FeltReportIntensityData)
        event_data = parsed_data.get_data()["20201230_0000049"]
        self.assertEqual(event_data["unid"], "20201230_0000049")
        self.assertGreater(len(event_data["intensities"]), 1)
        self.assertEqual(
            event_data["intensities"][0],
            {
                "lon": 14.4824,
                "lat": 46.0752,
                "raw": 1.0,
                "corrected": 1.0,
            },
        )

    def test_existing_zipfile_remains_open_after_parsing(self):
        archive = zipfile.ZipFile(io.BytesIO(zip_bytes()))
        try:
            self.parser.parse_testimonies(archive)
            self.assertIsNotNone(archive.fp)
            self.assertEqual(archive.namelist(), ["event-one.txt"])
        finally:
            archive.close()

    def test_zip_bytes_and_file_like_bytes_are_accepted(self):
        content = zip_bytes()
        for supplied_data in (content, io.BytesIO(content)):
            with self.subTest(input_type=type(supplied_data).__name__):
                parsed_data = self.parser.parse_testimonies(supplied_data)
                self.assertEqual(
                    parsed_data.get_data()["event-one"]["unid"],
                    "event-one",
                )

    def test_invalid_and_truncated_zip_content_is_rejected(self):
        valid_content = zip_bytes()
        for content in (b"not-a-zip", valid_content[:20]):
            with self.subTest(content=content):
                with self.assertRaisesRegex(
                        ValueError, "EMSC felt-intensity ZIP"):
                    self.parser.parse_testimonies(content)

    def test_empty_zip_archive_is_rejected(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w"):
            pass

        with self.assertRaisesRegex(ValueError, "EMSC.*archive is empty"):
            self.parser.parse_testimonies(buffer.getvalue())

    def test_archive_without_intensity_content_is_rejected(self):
        cases = (
            zip_bytes("not intensity data", filename="readme.md"),
            zip_bytes(
                "event_id|longitude|latitude",
                filename="events.csv",
            ),
        )
        for content in cases:
            with self.subTest(content=content):
                with self.assertRaisesRegex(
                        ValueError, "EMSC.*no CSV/text intensity content"):
                    self.parser.parse_testimonies(content)

    def test_empty_intensity_file_is_rejected(self):
        for content in (b"", b" \n\t"):
            with self.subTest(content=content):
                with self.assertRaisesRegex(
                        ValueError, "EMSC felt-intensity file.*empty"):
                    self.parser.parse_testimonies(zip_bytes(content))

    def test_missing_or_malformed_required_structure_is_rejected(self):
        cases = {
            "short header": "#event-one\n#comment",
            "missing event marker": intensity_text()[1:],
            "missing event identifier": intensity_text(event_id=""),
            "malformed comment": intensity_text().replace(
                "#thumbnails", "thumbnails"),
            "wrong header": intensity_text().replace("icorr", "corrected"),
        }
        for label, content in cases.items():
            with self.subTest(label=label):
                with self.assertRaisesRegex(
                        ValueError, "EMSC felt-intensity CSV"):
                    self.parser.parse_testimonies(zip_bytes(content))

    def test_singleton_and_multiple_rows_are_preserved(self):
        singleton = self.parser.parse_testimonies(
            zip_bytes(intensity_text(data_rows=["1,2,3,4"]))
        )
        multiple = self.parser.parse_testimonies(
            zip_bytes(intensity_text(data_rows=[
                "1,2,3,4",
                "5,6,7,8",
            ]))
        )

        self.assertEqual(
            len(singleton.get_data()["event-one"]["intensities"]),
            1,
        )
        self.assertEqual(
            len(multiple.get_data()["event-one"]["intensities"]),
            2,
        )

    def test_quoted_fields_and_numeric_zero_are_preserved(self):
        parsed_data = self.parser.parse_testimonies(
            zip_bytes(fixture_bytes("emsc-intensities.txt"))
        )

        rows = parsed_data.get_data()["event-one"]["intensities"]
        self.assertEqual(rows[0], {
            "lon": 0.0,
            "lat": 0.0,
            "raw": 0.0,
            "corrected": 0.0,
        })
        self.assertEqual(rows[1], {
            "lon": 14.4824,
            "lat": 46.0752,
            "raw": 1.0,
            "corrected": 2.0,
        })

    def test_extended_intensity_csv_ignores_metadata_companion(self):
        intensity_csv = "\n".join([
            "#20161030_0000029",
            "#thumbnails 1.0",
            "#Correction from Bossu et al. 2016",
            "#longitude,latitude,time,source,iraw,icorr",
            '13.0670,43.1951,"NaT UTC","",10,12.3',
        ])
        archive_content = zip_member_bytes({
            "20161030_0000029.csv": intensity_csv,
            "events.csv": (
                "event_id|longitude|latitude\n"
                "20161030_0000029|13.0670|43.1951"
            ),
            "LICENSE.txt": "provider license text",
            "felt-report-license.pdf": b"unrelated PDF content",
            "notes.md": "unrelated archive member",
        })

        parsed_data = self.parser.parse_testimonies(archive_content)

        self.assertEqual(
            set(parsed_data.get_data()),
            {"20161030_0000029"},
        )
        self.assertEqual(
            parsed_data.get_data()["20161030_0000029"]["intensities"],
            [{
                "lon": 13.067,
                "lat": 43.1951,
                "raw": 10.0,
                "corrected": 12.3,
            }],
        )

    def test_known_missing_intensity_markers_remain_absence(self):
        parsed_data = self.parser.parse_testimonies(
            zip_bytes(intensity_text(data_rows=[
                "1,2,NaN,null",
                "3,4,None,NaT",
            ]))
        )

        rows = parsed_data.get_data()["event-one"]["intensities"]
        self.assertIsNone(rows[0]["raw"])
        self.assertIsNone(rows[0]["corrected"])
        self.assertIsNone(rows[1]["raw"])
        self.assertIsNone(rows[1]["corrected"])

    def test_intensity_file_without_usable_rows_is_rejected(self):
        cases = (
            intensity_text(data_rows=[]),
            intensity_text(data_rows=["NaN,2,3,4"]),
            intensity_text(data_rows=["1,null,3,4"]),
        )
        for content in cases:
            with self.subTest(content=content):
                with self.assertRaisesRegex(
                        ValueError, "EMSC.*no usable data rows"):
                    self.parser.parse_testimonies(zip_bytes(content))

    def test_unrecognized_malformed_numeric_text_is_rejected(self):
        fields = (
            "bad,2,3,4",
            "1,bad,3,4",
            "1,2,bad,4",
            "1,2,3,bad",
        )
        for row in fields:
            with self.subTest(row=row):
                with self.assertRaisesRegex(
                        ValueError, "EMSC.*malformed"):
                    self.parser.parse_testimonies(
                        zip_bytes(intensity_text(data_rows=[row])))

    def test_structurally_inconsistent_csv_rows_are_rejected(self):
        for row in ("1,2,3", "1,2,3,4,5"):
            with self.subTest(row=row):
                with self.assertRaisesRegex(
                        ValueError, "EMSC.*same number of columns"):
                    self.parser.parse_testimonies(
                        zip_bytes(intensity_text(data_rows=[row])))

    def test_duplicate_required_intensity_column_is_rejected(self):
        content = intensity_text().replace(
            "#longitude,latitude,iraw,icorr",
            "#longitude,latitude,iraw,icorr,iraw",
        ).replace(
            "1,2,3,4",
            "1,2,3,4,5",
        )

        with self.assertRaisesRegex(
                ValueError, "EMSC.*exactly one.*iraw"):
            self.parser.parse_testimonies(zip_bytes(content))

    def test_malformed_quoted_csv_row_is_rejected(self):
        content = intensity_text(data_rows=['1,2,"3,4'])

        with self.assertRaisesRegex(ValueError, "EMSC.*malformed"):
            self.parser.parse_testimonies(zip_bytes(content))

    def test_dictionary_event_json_preserves_falsey_values(self):
        event_data = self.parser.parse(
            io.BytesIO(fixture_bytes("emsc-event.json"))
        )

        self.assertIsInstance(event_data, FeltReportEventData)
        self.assertEqual(event_data.get_event_id(), "event-one")
        self.assertEqual(event_data.get_longitude(), 0)
        self.assertEqual(event_data.get_latitude(), 0)
        self.assertEqual(event_data.get_magnitude(), 0)
        self.assertEqual(event_data.get_depth(), 0)
        self.assertEqual(event_data.get_event_nbtestimonies(), 0)

    def test_non_empty_list_event_json_selects_first_event(self):
        content = json.dumps([
            {"ev_id": "first-event", "ev_mag_value": 1},
            {"ev_id": "second-event", "ev_mag_value": 2},
        ]).encode("utf-8")

        event_data = self.parser.parse(content)

        self.assertEqual(event_data.get_event_id(), "first-event")
        self.assertEqual(event_data.get_magnitude(), 1)

    def test_malformed_and_empty_event_json_are_rejected(self):
        cases = (
            b"{",
            b"",
            b"   ",
            b"[]",
            b"{}",
        )
        for content in cases:
            with self.subTest(content=content):
                with self.assertRaisesRegex(
                        ValueError, "EMSC felt-report event JSON"):
                    self.parser.parse(content)

    def test_incompatible_event_json_shapes_are_rejected(self):
        cases = (
            json.dumps("event-one").encode("utf-8"),
            json.dumps(1).encode("utf-8"),
            json.dumps([["not", "an", "event"]]).encode("utf-8"),
        )
        for content in cases:
            with self.subTest(content=content):
                with self.assertRaisesRegex(
                        ValueError, "EMSC felt-report event JSON"):
                    self.parser.parse(content)

    def test_event_json_without_identifier_is_rejected(self):
        for content in (
                {"ev_mag_value": 4.2},
                [{"ev_mag_value": 4.2}],
                {"features": [{"properties": {"mag": 4.2}}]},
        ):
            with self.subTest(content=content):
                with self.assertRaisesRegex(
                        ValueError, "EMSC.*missing.*event identifier"):
                    self.parser.parse(json.dumps(content).encode("utf-8"))


if __name__ == "__main__":
    unittest.main()
