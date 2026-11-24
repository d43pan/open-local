import csv
import io
import json
import xml.etree.ElementTree as ET

from openlocal import cli, export, registry


def test_opml_is_valid_and_lists_only_feeds(reg):
    root = ET.fromstring(export.to_opml(reg))
    assert root.tag == "opml" and root.get("version") == "2.0"
    urls = {o.get("xmlUrl") for o in root.iter("outline") if o.get("xmlUrl")}
    assert urls == {"https://gazette.example.org/feed/", "https://harbourtimes.example.org/rss.xml"}  # calendars are not feeds
    assert all(o.get("htmlUrl") for o in root.iter("outline") if o.get("xmlUrl"))


def test_opml_for_one_place(reg):
    root = ET.fromstring(export.to_opml(reg, "XX/NO/birch"))
    assert {o.get("xmlUrl") for o in root.iter("outline") if o.get("xmlUrl")} == {"https://gazette.example.org/feed/", "https://harbourtimes.example.org/rss.xml"}
    assert "Birch" in root.find("head/title").text


def test_opml_escapes_names(reg):
    reg.sources[0]["name"] = 'A "quoted" <name> & more'
    ET.fromstring(export.to_opml(reg))


def test_json_round_trips(reg):
    again = registry.Registry(json.loads(export.to_json(reg)))
    assert again.places.keys() == reg.places.keys() and len(again.sources) == len(reg.sources)
    assert again.data["license"] == "CC0-1.0"


def test_csv_has_one_row_per_source(reg):
    rows = list(csv.DictReader(io.StringIO(export.to_csv(reg))))
    assert len(rows) == len(reg.sources)
    times = next(r for r in rows if r["id"] == "xx-no-alder-harbour-times")
    assert times["covers"] == "XX/NO/alder XX/NO/birch" and times["feeds"] == "https://harbourtimes.example.org/rss.xml"


def test_geojson(reg):
    doc = json.loads(export.to_geojson(reg))
    alder = next(f for f in doc["features"] if f["properties"]["id"] == "XX/NO/alder")
    assert alder["geometry"]["coordinates"] == [-71.17, 41.51] and alder["properties"]["sources"] == 3


def test_the_published_files_match_the_registry(capsys):
    assert cli.main(["build", "--check"]) == 0, capsys.readouterr().out
