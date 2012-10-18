import datetime
import time

from pynzb.base import BaseNZBParser, parse_date
from pynzb import ExpatNZBParser, ETreeNZBParser, LXMLNZBParser

SAMPLE_NZB = """<?xml version="1.0" encoding="iso-8859-1" ?>
<!DOCTYPE nzb PUBLIC "-//newzBin//DTD NZB 1.0//EN" "http://www.newzbin.com/DTD/nzb/nzb-1.0.dtd">
<nzb xmlns="http://www.newzbin.com/DTD/2003/nzb">
 <file poster="Joe Bloggs (bloggs@nowhere.example)" date="1071674882" subject="Here's your file!  abc-mr2a.r01 (1/2)">
   <groups>
     <group>alt.binaries.newzbin</group>
     <group>alt.binaries.mojo</group>
   </groups>
   <segments>
     <segment bytes="102394" number="1">123456789abcdef@news.newzbin.com</segment>
     <segment bytes="4501" number="2">987654321fedbca@news.newzbin.com</segment>
   </segments>
 </file>
</nzb>"""

def test_parse_date():
    parser = BaseNZBParser()
    date = parse_date("1071674882")
    assert date == datetime.date(2003, 12, 17)


def assert_sample_nzb(f):
    assert f.poster == 'Joe Bloggs (bloggs@nowhere.example)'
    assert f.date == parse_date(1071674882)
    assert f.subject == "Here's your file!  abc-mr2a.r01 (1/2)"
    assert sorted(f.groups) == sorted(['alt.binaries.newzbin', 'alt.binaries.mojo'])
    first_segment = sorted(f.segments, key=lambda s: s.number)[0]
    assert first_segment.bytes == 102394
    assert first_segment.number == 1
    assert first_segment.message_id == '123456789abcdef@news.newzbin.com'
    second_segment = sorted(f.segments, key=lambda s: s.number)[1]
    assert second_segment.bytes == 4501
    assert second_segment.number == 2
    assert second_segment.message_id == '987654321fedbca@news.newzbin.com'


def test_expat():
    parser = ExpatNZBParser()
    files = parser.parse(SAMPLE_NZB)
    assert_sample_nzb(files[0])


def test_etree():
    parser = ETreeNZBParser()
    files = parser.parse(SAMPLE_NZB)
    assert_sample_nzb(files[0])


def test_lxml():
    parser = LXMLNZBParser()
    files = parser.parse(SAMPLE_NZB)
    assert_sample_nzb(files[0])