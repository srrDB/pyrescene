import datetime
import time

try:  #  Python < 3
    basestring = basestring
except NameError:  # Python 3
    basestring = str

def parse_date(date):
    if isinstance(date, basestring):
        date = int(date)
    gmtime = time.gmtime(date)
    return datetime.date(gmtime.tm_year, gmtime.tm_mon, gmtime.tm_mday)

class NZBSegment(object):
    def __init__(self, bytes, number, message_id=None):
        self.bytes = int(bytes)
        self.number = int(number)
        if message_id:
            self.message_id = message_id

    def set_message_id(self, message_id):
        self.message_id = message_id

class NZBFile(object):
    def __init__(self, poster, date, subject, groups=None, segments=None):
        self.poster = poster
        self.date = parse_date(date)
        self.subject = subject
        self.groups = groups or []
        self.segments = segments or []

    def add_group(self, group):
        self.groups.append(group)

    def add_segment(self, segment):
        self.segments.append(segment)

class BaseNZBParser(object):
    def parse(self, xml):
        raise NotImplementedError

class BaseETreeNZBParser(BaseNZBParser):
    def get_etree_iter(self, xml, et=None):
        raise NotImplementedError

    def parse(self, xml):
        context = self.get_etree_iter(xml)
        files, current_file, current_segment = [], None, None

        for event, elem in context:
            if event == "start":
                # If it's an NZBFile, create an object so that we can add the
                # appropriate stuff to it.
                if elem.tag == "{http://www.newzbin.com/DTD/2003/nzb}file":
                    current_file = NZBFile(
                        poster=elem.attrib['poster'],
                        date=elem.attrib['date'],
                        subject=elem.attrib['subject']
                    )

            elif event == "end":
                if elem.tag == "{http://www.newzbin.com/DTD/2003/nzb}file":
                    files.append(current_file)

                elif elem.tag == "{http://www.newzbin.com/DTD/2003/nzb}group":
                    current_file.add_group(elem.text)

                elif elem.tag == "{http://www.newzbin.com/DTD/2003/nzb}segment":
                    current_file.add_segment(
                        NZBSegment(
                            bytes=elem.attrib['bytes'],
                            number=elem.attrib['number'],
                            message_id=elem.text
                        )
                    )
                # Clear the element, we don't need it any more.
                elem.clear()
        return files
