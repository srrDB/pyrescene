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

"""
Split one big NZB file to the different releases based on the subject. 
	:sek9: 
	
Changelog:
0.1: initial version (2011-12-24)
0.2: (2012-01-03)
 - no pretty XML anymore (bug in minidom)
 - make it work correct (missing nfo files)
 - that introduced slowness: made if fast again
0.3: (2012-04-21)
0.4: (2012-09-28)
 - memory usage improvement
 - work with bad subject headers

"""

import os
import sys
import optparse
import re
import nzb_utils
import unittest
	
SEK9 = "\[:SEK9:\]\[.*\]-\[:(?P<relname>.*):\].*"
# (Attack.The.Block.2011.NL.PAL.DVDR-REWIND Powered by Cheese)
# [Just.Go.With.It.2011.PAL.NL.DVDr-PaTHe Powered by Cheese]
CHEESE = "[\[\(](?P<relname>.*?)[\] \)].*"
NORDIC = "(?P<relname>.+?-.+?) .*" # MinorThreat
UHQ = ".*< ?(?P<relname>.{17,}?) ?>.*"
LOU = ".*Sponsored by SSL-News.info>>( -)? ? (presents )?(?P<relname>.*?)( -|- ).*"
GOU = ".*>ghost-of-usenet.org<ENG-DVDR><< (?P<relname>.*?) >>.*"
TN = ".*(www.Thunder-News.org) >(?P<relname>.*?)< >Sponsored by Secretusenet.*"
TEEVEE = ".*\[ (?P<relname>.*) \].*"

#TODO: do like nzbsrr.py and try them all
REGEX_LIST = [SEK9, TN, GOU, LOU, TEEVEE, UHQ, CHEESE, NORDIC]
REGEX = TEEVEE

# we assume that all files of a release are together (to improve memory usage)

#def main(options, args):
#	output_dir = args[1]
#	reldict = {} # contains all the nzb stuff in memory
#
#	# group everything together
#	for nzb_file in nzb_utils.read_nzb(args[0]):
#		match = re.match(REGEX, nzb_file.subject)
#		file_name = nzb_utils.parse_name(nzb_file.subject)
#		ln = longest_name(nzb_file.subject, file_name)
#
#		if len(file_name): # and file_name[-4:] == ".nfo":
#			# decide which of the three options is the best
#			try:
#				base = grab_base_name(file_name)
#			except:
#				print("Failed: %s" % nzb_file.subject)
#				continue
#			
#			if match:
#				regexrelname = match.group("relname")
#				
#				# 5: .cd1.
#				if len(base) < len(regexrelname) + 5:
#					base = regexrelname
#			else:
#				if len(base) < len(ln):
#					if '"' not in ln:
#						base = ln
#				
##				if file_name in regexrelname:
##					match = ln
##					if file_name in match:
##						match = None
##						
##				if len(match.group("relname")) < len(ln):
##					match = ln
#			
##			if match:
##				try:
##					rel = match.group("relname")
##				except AttributeError:
##					rel = match
#				
#			rel = base
#			rel = rel.replace('?', '_')
#			rel = rel.replace('*', '_')
#			rel = rel.replace(':', '_')
#			rel = rel.replace('"', '_')
#			rel = rel.replace('<', '_')
#			rel = rel.replace('>', '_')
#			rel = rel.replace('|', '_')
#			rel = rel.replace('/', '_')
#			rel = rel.replace('\\', '_')
#			files = reldict.setdefault(rel, [])
#			files.append(nzb_file)
#			reldict[rel] = files
##			else:
##				# trying grouping based on (borked) file names
##				
##					
##	#			if len(base) < len(longest_name(nzb_file.subject)):
##	#				base = longest_name(nzb_file.subject)
##	
##	
##				files = reldict.setdefault(base, [])
##				files.append(nzb_file)
##				reldict[base] = files
#		else:
#			print("Failed: %s" % nzb_file.subject)
#
#	for release in reldict:
#		new = os.path.join(output_dir, release.replace('"', '') + ".nzb")
#		with open(new, "w") as nzb:
#			doc = nzb_utils.empty_nzb_document()
#			for rfile in reldict[release]:
#				nzb_utils.add_file(doc, rfile)
#			nzb.write(nzb_utils.get_xml(doc))		
	
def main(options, args):
	output_dir = args[1]
	reldict = {} # contains all the nzb stuff in memory
	current_rel = ""
	
	# group everything together
	for nzb_file in nzb_utils.read_nzb(args[0]):
		for regex in REGEX_LIST:
			match = re.match(regex, nzb_file.subject)
			if match:
				break
		file_name = nzb_utils.parse_name(nzb_file.subject)
		ln = longest_name(nzb_file.subject, file_name)

		if len(file_name): # and file_name[-4:] == ".nfo":
			# decide which of the three options is the best
			try:
				base = grab_base_name(file_name)
			except:
				print("Failed: %s" % nzb_file.subject)
				continue
			
			if match:
				regexrelname = match.group("relname")
				
				base = regexrelname
#				# 5: .cd1.
#				# 7: -sample
#				if len(base) < len(regexrelname) + 8:
#					base = regexrelname
			else:
				if len(base) < len(ln):
					if '"' not in ln:
						base = ln
			rel = base
			rel = rel.replace('?', '_')
			rel = rel.replace('*', '_')
			rel = rel.replace(':', '_')
			rel = rel.replace('"', '_')
			rel = rel.replace('<', '_')
			rel = rel.replace('>', '_')
			rel = rel.replace('|', '_')
			rel = rel.replace('/', '_')
			rel = rel.replace('\\', '_')
			# no _ at beginning or end e.g. : not part of rel name
			rel = rel.strip("_")
			
			if rel != current_rel:
				try:
					new = os.path.join(output_dir, 
					                   current_rel.replace('"', '') + ".nzb")
					with open(new, "w") as nzb:
						doc = nzb_utils.empty_nzb_document()
						for rfile in reldict.pop(current_rel):
							nzb_utils.add_file(doc, rfile)
						nzb.write(nzb_utils.get_xml(doc))
				except KeyError:
					pass
				current_rel = rel
			
			files = reldict.setdefault(rel, [])
			files.append(nzb_file)
			reldict[rel] = files
		else:
			print("Failed: %s" % nzb_file.subject)
			
def grab_base_name(filename):
	#"invandraren-walla25.sfv" (1/1)
	#"invandraren-walla25.vol00+01.par2" (7/7)
	#"invandraren-hung.s01d01.proper.r09-B4E" 2H2H (79/79)
	#"invandraren-hung.s01d01.proper.r10-B4E" 2H2H (79/79)
	suf = ["-VIP_", "-VIP_", "-VIP", "-B4E", "-REPOST-PIV", "-vip", "VIP-"]
	for suffix in suf:
		filename = filename.replace(suffix, "")
	filename = filename.strip("_-")
	m = re.match("(.*?)(.part\d\d\d?.rar|.par2|.(r|s)\d\d|.sfv|.srr|.srs|"
				".vob|.mkv|.avi|.mp4|.vol\d.*|\.rar|.nfo|.nzb|.jpg|.png|"
				".\d\d\d)$", filename, re.I)
	return m.group(1)

def longest_name(subject, file_name):
	subject = subject.replace("[", " ")
	subject = subject.replace("]", " ")
	subject = subject.replace("<", " ")
	subject = subject.replace(">", " ")
	subject = subject.replace('?', ' ')
	subject = subject.replace('*', ' ')
	subject = subject.replace(':', ' ')
	subject = subject.replace('"', ' ')
	subject = subject.replace('|', ' ')
	subject = subject.replace('/', ' ')
	subject = subject.replace('\\', ' ')
	strgroups = subject.split(" ")
	length = 0
	relname = ""
	for group in strgroups:
		if len(group) > length and not file_name in group:
			relname = group
			length = len(group)
	return relname

class TestRegEx(unittest.TestCase):
	def test_grab(self):
		self.assertEqual("invandraren-the.big.bang.theory.s4d1",
				grab_base_name("_invandraren-the.big.bang.theory.s4d1.r36_"))
		self.assertEqual("invandraren-v.s2d2b",
				grab_base_name("_invandraren-v.s2d2b.r33-VIP_"))
		
	def test_longest_name(self):
		ln = '''[17899]-[#a.b.hdtv.x264@EFNet]-[ Africa.United.2010.720p.BluRay.x264-iNVANDRAREN ]- "invandraren-africa.united.720p.sample.vol063+57.par2"'''
		self.assertEqual("Africa.United.2010.720p.BluRay.x264-iNVANDRAREN",
				longest_name(ln, "invandraren-africa.united.720p.sample.vol063+57.par2"))

if __name__ == '__main__':
	parser = optparse.OptionParser(
		usage="Usage: %prog [nzb file] [output dir]'\n"
		"This tool will split a large NZB file.\n",
		version="%prog 0.4 (2012-09-28)") # --help, --version

	# no arguments given
	if len(sys.argv) < 2:
		print(parser.format_help())
	else:
		(options, args) = parser.parse_args()
		main(options, args)
