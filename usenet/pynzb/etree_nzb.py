from pynzb.base import BaseETreeNZBParser, NZBFile, NZBSegment
from io import BytesIO

try:
    import cElementTree as etree
except ImportError:
    try:
        from xml.etree import ElementTree as etree
    except ImportError:
        raise ImportError("You must have either Python 2.5 or cElementTree " +
            "installed before you can use the etree NZB parser.")

class ETreeNZBParser(BaseETreeNZBParser):
    def get_etree_iter(self, xml, et=etree):
        return iter(et.iterparse(BytesIO(xml), events=("start", "end")))