from pynzb.expat_nzb import ExpatNZBParser

try:
    from pynzb.etree_nzb import ETreeNZBParser
except ImportError:
    ETreeNZBParser = None
try:
    from pynzb.lxml_nzb import LXMLNZBParser
except ImportError:
    LXMLNZBParser = None

# Set up the parser based on speed precedence
if LXMLNZBParser is not None:
    nzb_parser = LXMLNZBParser()
elif ETreeNZBParser is not None:
    nzb_parser = ETreeNZBParser()
else:
    nzb_parser = ExpatNZBParser()