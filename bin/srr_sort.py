#!/usr/bin/env python
# -*- coding: utf-8 -*-

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

import optparse
import sys
import os
import glob
import rar
import re
from os.path import join, dirname, realpath

# for running the script directly from command line
sys.path.append(join(dirname(realpath(sys.argv[0])), '..', 'rescene'))

import rescene

def check_compression(srr_file):
	fb = None
	for block in rar.RarReader(srr_file):
		if block.rawtype == rar.BlockType.RarPackedFile:
			fb = block
			break
	if fb and fb.compression_method != rar.COMPR_STORING:
		return True
	return False
		
def check_empty(srr_file):
	for block in rar.RarReader(srr_file):
		if block.rawtype == rar.BlockType.RarPackedFile:
			return False
	return True

def check_image(srr_file, noproof):
	images = (".jpg", ".png", ".bmp", ".gif", "jpeg")
	for block in rar.RarReader(srr_file):
		if (block.rawtype == rar.BlockType.SrrStoredFile and
			os.path.splitext(block.file_name)[1] in images):
			if noproof and "proof" in block.file_name.lower():
				return False
			return True
	return False

def check_repack(srr_file):
	tmatch = ("rpk", "repack", "-r.part01.rar", "-r.rar")
	for block in rar.RarReader(srr_file):
		if block.rawtype == rar.BlockType.SrrRarFile:
			matchf = lambda keyword: keyword in block.file_name 
			if len(filter(matchf, tmatch)):
				return True
	return False

def check_nfos(srr_file):
	for block in rar.RarReader(srr_file):
		nfo_count = 0
		if (block.rawtype == rar.BlockType.SrrStoredFile and
			block.file_name[-4:].lower() == ".nfo"):
			nfo_count += 1
	return False if nfo_count <= 1 else True

def check_for_possible_nonscene(srr_file):
	for block in rar.RarReader(srr_file):
		if (block.rawtype == rar.BlockType.SrrRarFile and
			block.file_name != block.file_name.lower()):
			return True
	return False

def check_availability_stored_files(srr_file):
	for block in rar.RarReader(srr_file):
		if block.rawtype == rar.BlockType.SrrStoredFile:
			return False
	return True

def check_for_no_ext(srr_file, extention):
	for block in rar.RarReader(srr_file):
		if (block.rawtype == rar.BlockType.SrrStoredFile and
			block.file_name.lower()[-4:] == extention):
			return False
	return True
		
rar_sizes = 0 #bytes

def check(srr_file):
	try:
		result = False
		if options.verify or options.multiple:
			info = rescene.info(srr_file)
			global rar_sizes
			rar_sizes += sum([info['rar_files'][f].file_size 
			                  for f in info['rar_files']])
			if options.multiple:
				sets = []
				for f in info["rar_files"]:
					ms = "^(.*?)(.part\d+.rar|(.[rstuv]\d\d|.rar))$"
					base = re.match(ms, f, re.IGNORECASE).group(1)
					if not base in sets:
						sets.append(base)
				result |= len(info["archived_files"]) > len(sets)
				# print(sets) # useful to check ordering
			
		if options.dirfix:
			if "dirfix" in srr_file.lower() or "nfofix" in srr_file.lower():
				print(srr_file)
		if options.lowercase:
			group = srr_file[:-4].rsplit("-")[-1]
			if group == group.lower():
				result |= True
			if "." in group: # does not have a group name
				result |= True
			fn = os.path.split(srr_file)[1]
			if fn == fn.lower():
				result |= True
				
		if options.compressed:
			result |= check_compression(srr_file)
		if options.empty:
			result |= check_empty(srr_file)
		if options.image or options.noproof:
			result |= check_image(srr_file, options.noproof)
		if options.repack:
			result |= check_repack(srr_file)
		if options.nfos:
			result |= check_nfos(srr_file)
		if options.peer2peer:
			result |= check_for_possible_nonscene(srr_file)
		if options.nofiles:
			result |= check_availability_stored_files(srr_file)
		if options.nosfv:
			result |= check_for_no_ext(srr_file, ".sfv")
		if options.nonfo:
			result |= check_for_no_ext(srr_file, ".nfo")
		if result and options.output_dir:
			print("Moving %s." % srr_file)
			srr_name = os.path.basename(srr_file)
			# move the SRR to the given directory
			os.renames(srr_file, os.path.join(options.output_dir, srr_name))
		if result:
			print(os.path.basename(srr_file))
	except (EnvironmentError, Exception):
		# the storing of a srr_file failed -> corrupt SRR
		print("Something wrong with reading %s" % srr_file)
		print(sys.exc_info())
		
def main(options, args):
	for element in args:
		if os.path.isdir(element):
			for srr_file in glob.iglob(element + "/*.srr"):
				check(srr_file)
		elif os.path.isfile(element) and element[-4:] == ".srr":
			check(element)
		else:
			print("WTF are you supplying me?")

	if rar_sizes:
		print("%d bytes" % rar_sizes)
		print("%.2f KiB" % (rar_sizes / 1024.0))
		print("%.2f MiB" % (rar_sizes / 1024.0 / 1024.0))
		print("%.2f GiB" % (rar_sizes / 1024.0 / 1024.0 / 1024.0))
		print("%.2f TiB" % (rar_sizes / 1024.0 / 1024.0 / 1024.0 / 1024.0))
			
if __name__ == '__main__':
	parser = optparse.OptionParser(
		usage="Usage: %prog [directories] [srrs] [options]'\n"
		"This tool will list compressed, empty or SRR files with images.\n"
		"It optionally moves them to a given output directory.",
		version="%prog 1.0 (2012-09-20)") # --help, --version
	
	parser.add_option("-c", "--compressed", help="list compressed SRRs",
					  action="store_true", dest="compressed", default=False)	
	parser.add_option("-e", "--empty", help="list SRRs with no RAR data",
					  action="store_true", dest="empty", default=False)
	

	parser.add_option("-v", "--verify", help="check whole SRR for correctness "
					  "and return full RAR sizes at the end",
					  action="store_true", dest="verify", default=False)
	parser.add_option("-t", "--nfos", help="two or more NFOs",
					  action="store_true", dest="nfos", default=False)
	parser.add_option("-p", "--noproof", help="list SRRs with images that "
						"do not contain the word proof",
					  action="store_true", dest="noproof", default=False)
	parser.add_option("-i", "--image", help="list SRRs with stored images",
					  action="store_true", dest="image", default=False)

	parser.add_option("-f", "--nofiles", help="list SRRs if no files are stored",
					  action="store_true", dest="nofiles", default=False)
	parser.add_option("-m", "--multiple", 
	                  help="list SRRs with multiple archived files",
					  action="store_true", dest="multiple", default=False)
	
	parser.add_option("-s", "--nosfv", help="list SRRs without SFV",
					  action="store_true", dest="nosfv", default=False)
	parser.add_option("-n", "--nonfo", help="list SRRs without NFO",
					  action="store_true", dest="nonfo", default=False)
	
	parser.add_option("-r", "--repack", help="list SRRs with -rpk., -r. in RAR name",
					  action="store_true", dest="repack", default=False)
	parser.add_option("-2", "--p2p", help="not all RARs are lower case",
					  action="store_true", dest="peer2peer", default=False)
	parser.add_option("-l", help="list lower case/no group names",
					  action="store_true", dest="lowercase", default=False)
	parser.add_option("-d", "--dirfix", help="dirfixes and nfofixes",
					  action="store_true", dest="dirfix", default=False)
	
	parser.add_option("-o", dest="output_dir", metavar="DIRECTORY",
					help="moves the matched SRR files to the given DIRECTORY")
	
	# no arguments given
	if len(sys.argv) < 2:
		print(parser.format_help())
	else:
		(options, args) = parser.parse_args()
		main(options, args)
		
""" 
>>> list = os.listdir(".")
>>> def get_name(name):
...     return name[:-4].rsplit("-")[-1]
...
>>> get_name("Zebraman.2.Attack.On.Zebra.City.2011.720p.BluRay.x264-Japhson.srr")
'Japhson'
>>> for e in list:
...     n = get_name(e)
...     if n == n.lower():
...             print(e)
...
"""