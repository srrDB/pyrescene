from xml.parsers import expat

from pynzb.base import BaseNZBParser, NZBFile, NZBSegment

class ExpatNZBParser(BaseNZBParser):
    def start_element(self, name, attrs):
        if name == 'file':
            self.current_file = NZBFile(
                poster=attrs['poster'],
                date=attrs['date'],
                subject=attrs['subject']
            )
        if name == 'segment':
            self.current_segment = NZBSegment(
                bytes=attrs['bytes'],
                number=attrs['number']
            )

    def end_element(self, name):
        if name == 'file':
            self.files.append(self.current_file)
        elif name == 'group':
            self.current_file.add_group(self.current_data)
        elif name == 'segment':
            self.current_segment.set_message_id(self.current_data)
            self.current_file.add_segment(self.current_segment)

    def char_data(self, data):
        self.current_data = data

    def parse(self, xml):
        self.files = []
        parser = expat.ParserCreate()
        parser.StartElementHandler = self.start_element
        parser.EndElementHandler = self.end_element
        parser.CharacterDataHandler = self.char_data
        parser.Parse(xml)
        return self.files
