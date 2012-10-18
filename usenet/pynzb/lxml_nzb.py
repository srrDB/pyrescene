from pynzb.base import BaseETreeNZBParser, NZBFile, NZBSegment

try:
    from lxml import etree
except ImportError:
    raise ImportError("You must have lxml installed before you can use the " +
        "lxml NZB parser.")

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

class LXMLNZBParser(BaseETreeNZBParser):
    def get_etree_iter(self, xml, et=etree):
        return iter(et.iterparse(StringIO(xml), events=("start", "end")))