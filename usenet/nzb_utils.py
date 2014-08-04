#!/usr/bin/env python
# -*- coding: latin-1 -*-

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>

# https://docs.newzbin2.es/index.php/Newzbin:NZB_Specs

import pynzb # http://pypi.python.org/pypi/pynzb/
import os
import io
import re
import time
import datetime
from xml.dom import minidom

def read_nzb(nzb_file):
	""" Returns empty list for empty NZB files. """
	print("Reading %s." % os.path.basename(nzb_file))
	def parse(pnzb_file):
		try: # file on disk
			with open(pnzb_file, "rb") as file:
				return pynzb.nzb_parser.parse(file.read())
		except: # an open file object
			return pynzb.nzb_parser.parse(pnzb_file.read())

	try:
		return parse(nzb_file)
	except Exception:
		print("Parsing the nzb file failed. Trying to fix invalid XML.")
		# Problem with the ampersand.
		# newsmangler doesn't properly escape the & in the NZB
		# http://www.powergrep.com/manual/xmpxmlfixentities.html
		XML_AMP_FIX = b"&(?!(?:[a-z]+|#[0-9]+|#x[0-9a-f]+);)"
		fixed_nzb = io.BytesIO()
		with open(nzb_file, "rb") as file:
			for line in file.readlines():
				line = re.sub(XML_AMP_FIX, b"&amp;", line)
				LATIN1_OUML = b"\xF6"
				line = re.sub(b"&ouml;", LATIN1_OUML, line)
				# invalid XML characters from NewsLeecher
				line = re.sub(b"\00", b"", line)
				fixed_nzb.write(line)
		# do not fail on empty NZB files
		if fixed_nzb.tell() == 0:
			print("Empty NZB file: %s" % os.path.basename(nzb_file))
			return []
		fixed_nzb.seek(0)
		return parse(fixed_nzb)
	
def parse_name(subject):
	""" Grabs the file name from the subject of the Usenet posting. 
	Return the whole subject if the file name isn't parseable. 
	&quot; must be replaced by " for this to work. """
	match = re.search('''"(.*)"''', subject)
	if match:
		return match.group(1).strip('"')
	else:
		# "Because the poster used a non-standard subject line, the system was 
		# unable to determine the filename with certainty."
		match = re.search(".*(\]-| )(?P<filename>.*) [\d/\(\)]+", subject)
		if match:
			return match.group("filename")
		else:
			return subject

"""
NZBFile Objects
===============

All of the parsers return ``NZBFile`` objects, which are objects with the
following properties:

``poster``:
    The name of the user who posted the file to the newsgroup.

``date``:
    A ``datetime.date`` representation of when the server first saw the file.

``subject``:
    The subject used when the user posted the file to the newsgroup.

``groups``:
    A list of strings representing the newsgroups in which this file may be
    found.

``segments``:
    A list of ``NZBSegment`` objects talking about where to get the contents
    of this file.


NZBSegment Objects
==================

Each ``NZBFile`` has a list of ``NZBSegment`` objects, which include
information
on how to retrieve a part of a file.  Here's what you can find on an
``NZBSegment`` object:

``number``:
    The number of the segment in the list of files.

``bytes``:
    The size of the segment, in bytes.

``message_id``:
    The Message-ID of the segment (useful for retrieving the full contents)
"""

# fix pynzb library
def _parse_date(date):
	if isinstance(date, pynzb.base.basestring):
		date = int(date)
	return datetime.datetime.fromtimestamp(date)
pynzb.base.parse_date = _parse_date

# add compare functionality
def _equality_test(self, other):
	try:
		return (self.bytes == other.bytes and
			self.number == other.number and
			self.message_id == other.message_id)
	except AttributeError:
		return (self.bytes == other.bytes and
			self.number == other.number)
pynzb.base.NZBSegment.__eq__ = _equality_test

# pynzb library only supports parsing
#'add_group', 'add_segment', 'date', 'groups', 'poster', 'segments', 'subject'

def empty_nzb_document():
	""" Creates xmldoc XML document for a NZB file. """
	# http://stackoverflow.com/questions/1980380/how-to-render-a-doctype-with-pythons-xml-dom-minidom
	imp = minidom.getDOMImplementation()
	dt = imp.createDocumentType("nzb", "-//newzBin//DTD NZB 1.1//EN", 
	                            "http://www.newzbin.com/DTD/nzb/nzb-1.1.dtd")
	doc = imp.createDocument("http://www.newzbin.com/DTD/2003/nzb", "nzb", dt)
	# http://stackoverflow.com/questions/2306149/how-to-write-xml-elements-with-namespaces-in-python
	doc.documentElement.setAttribute('xmlns', 
	                                 'http://www.newzbin.com/DTD/2003/nzb')
	return doc

def get_pretty_xml(document):
	""" NZB will have bugs if used with the wrong Python version:
	http://bugs.python.org/issue1777134 """
	return document.toprettyxml(encoding="UTF-8")

def get_xml(document):
	return document.toxml("UTF-8")

def _date_to_posix(date):
	""" date: datetime.datetime object """
	posix = time.mktime(date.timetuple())
	return str(int(posix))

def add_file(document, nzb_file):
	""" document: xml.dom.minidom.Document object """
	top_element = document.documentElement
	file_element = document.createElement("file")
	
	# add file attributes
	file_element.setAttribute("poster", nzb_file.poster)
	file_element.setAttribute("date", _date_to_posix(nzb_file.date))
	file_element.setAttribute("subject", nzb_file.subject)
	
	# groups
	groups = document.createElement("groups")
	for group in nzb_file.groups:
		g = document.createElement("group")
		g.appendChild(document.createTextNode(group))
		groups.appendChild(g)
	file_element.appendChild(groups)	
	
	# segments
	segments = document.createElement("segments")
	for segment in nzb_file.segments:
		s = document.createElement("segment")
		s.setAttribute("bytes", str(segment.bytes))
		s.setAttribute("number", str(segment.number))
		s.appendChild(document.createTextNode(segment.message_id))
		segments.appendChild(s)
	file_element.appendChild(segments)	
	
	top_element.appendChild(file_element)	
	return document

def list_filenames(nzb_file):
	return [(parse_name(f.subject), f.date) for f in read_nzb(nzb_file)]

""" Really weird:
 <groups>
  <group>alt.binaries.x264</group>
 <segments>
 </groups> 
"""	
