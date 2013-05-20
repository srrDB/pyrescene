#!/usr/bin/env python
# -*- coding: utf-8 -*-

import rar
import zlib
import struct
import rescene
import os

#filenb = 12 # r11


#dir = "C:/dump/"
#avi = dir + "exvid-mzktv-cd2.avi"
#r09 = dir + "exvid-mzktv-cd2.r09"
#r10 = dir + "exvid-mzktv-cd2.r10"
#extract = dir + "r11extract.bin"
#hbefore = dir + "r10headers_before.bin"
#hafter = dir + "r10headers_after.bin"
#hbeforefix = dir + "r10headers_before_fix.bin"
#hafterfix = dir + "r10headers_after_fix.bin"
#
#beforerr = dir + "r11headers_data.bin" # hbeforefix + extract
#rrblock = dir + "r11headers_data_recoveryrecord.bin"
#resultfull = dir + "exvid-mzktv-cd2.r11"
#
#start = 174628160 + 16 # 0xa689d40
#end = 189180524 # 0xb46aa6c
#amount = 14552348 # amount of data stored in one volume
#assert start == amount*filenb == 174628176 # rar, r00, r01...r10
#assert end - start == amount

# try r10
#filenb = 11
#start = amount*filenb
#end = start + amount

filenb = 21 # r20
dir = "C:/dump/sha0lin"
avi = dir + "exvid-mzktv-cd2.avi"
r09 = dir + "exvid-mzktv-cd2.r09"
r10 = dir + "sinx-man.vs.wild.s03e04.south.dakota_x264.r20"
extract = dir + "r11extract.bin"
hbefore = dir + "r10headers_before.bin"
hafter = dir + "r10headers_after.bin"
hbeforefix = dir + "r10headers_before_fix.bin"
hafterfix = dir + "r10headers_after_fix.bin"

beforerr = dir + "r11headers_data.bin" # hbeforefix + extract
rrblock = dir + "r11headers_data_recoveryrecord.bin"
resultfull = dir + "sinx-man.vs.wild.s03e04.south.dakota_x264.r21"


amount = 49505896 # amount of data stored in one volume
start = amount * filenb
end = start + amount


def extract_part():
	with open(avi, "rb") as af:
		af.seek(start)
		with open(extract, "wb") as data:
			data.write(af.read(amount))

def get_headers_r10():
	""" hbefore and hafter
	RAR Marker 0 7
	RAR Archive Header 7 13
	RAR File 14 56
	RAR New-format subblock de0d68 54
	RAR Archive end e4e1ac 20"""

	index = 1
	before = after = b""
	for block in rar.RarReader(r10).read_all():
		# first 3 blocks
		if index in range(1, 4):
			before += block.bytes()
		if index == 5:
			after = block.bytes()
		index += 1
	with open(hbefore, "wb") as hb:
		hb.write(before)
	with open(hafter, "wb") as ha:
		ha.write(after)

def calc_crc(new_data, previous_crc=None):   
	"""calculate the crc needed in the header from the file/RR
	previous_volume: not used: not a running crc!"""
#	for block in rar.RarReader(previous_volume).read_all():
#		if block.rawtype == rar.BlockType.RarPackedFile:
#			start = block.file_crc
#			
	# we only look at the stored data in the current file
	if previous_crc:
		crc = zlib.crc32(new_data, previous_crc) & 0xFFFFFFFF
	else:
		crc = zlib.crc32(new_data) & 0xFFFFFFFF
#	print("Hex file r10 (previous): %x" % start)
#	print("Hex file r11 (calculated): %x" % crc)
	print("Hex of data: %x" % crc)
	return crc
def test_calc_crc():
	# test the above function
	# r09: f46b957c
	# r10: ce576d06
	print("test r09-r10 new crc calculation:")
	for block in rar.RarReader(r10).read_all():
		if block.rawtype == rar.BlockType.RarPackedFile:
			amount = block.packed_size
			start = block.block_position + block.header_size
	with open(r10, "rb") as data:
		data.seek(start)
		assert 0xce576d06 == calc_crc(data.read(amount)) #, r09) 
#test_calc_crc()
	



def fix_file_header():
	""" reads 'extract'ed data to fix the headers before the data """
	# does not work yet:
	with open(extract, "rb") as data:
		crc = calc_crc(data.read())
		
#	print(crc) # 4229429904
#	print(0x034e3c88)
#	assert hex(crc) == 0x034e3c88 #FAILS!
	
	fixed_data = b""
	rr = rar.RarReader(hbefore)
	block = next(rr)
	while block.rawtype != rar.BlockType.RarPackedFile:
		fixed_data += block.bytes()
		block = next(rr)
	
	# the block to fix
	data = block.bytes()
	if block.rawtype == rar.BlockType.RarPackedFile:
		before = block.bytes()[:7+9]
		after = block.bytes()[7+9+4:]
		bytes = before + struct.pack("<I", crc) + after
		header_crc = zlib.crc32(bytes[2:]) & 0xFFFF
		bytes = struct.pack("<H", header_crc) + bytes[2:]
	fixed_data += bytes
		
	# write fixed file
	with open(hbeforefix, "wb") as hb:
		hb.write(fixed_data)
		
def create_after(data_before):
	""" 'beforerr' must be created (all data before this last block) """
	with open(hafter, "rb") as ha:
		bytes = ha.read()
	before = bytes[:7]
	after = bytes[7+4+2:]
	
	# everything except the last 20 bytes
	with open(data_before, "rb") as re:
		crc_all = calc_crc(re.read())
	
	# change 12 to the next volume
	bytes = (before + struct.pack("<I", crc_all) + 
			 struct.pack("<H", filenb) + after)
	header_crc = zlib.crc32(bytes[2:]) & 0xFFFF
	bytes = struct.pack("<H", header_crc) + bytes[2:]

	with open(hafterfix, "wb") as ha:
		ha.write(bytes)



def join_data(to_file, first, second):
	with open(to_file, "wb") as before:
		with open(first, "rb") as hb:
			before.write(hb.read())
		with open(second, "rb") as extr:
			before.write(extr.read())

def calculate_recovery_record():
	"""rr header: has a data crc of the recovery record data
	crc block header: is changed too because of the above"""
#	for block in rar.RarReader(r09).read_all():
#		if block.rawtype == rar.BlockType.RarNewSub:
#			r09bytes = block.bytes()
	for block in rar.RarReader(r10).read_all():
		if block.rawtype == rar.BlockType.RarNewSub:
			r10bytes = block.bytes()
			r10block = block
			print(block.explain())
	"""Block: RAR New-format subblock; offset: 0xDE0D68 (14552424 bytes)
	|Header bytes: d2437a00c036000ed406000ed4060002cd298b1a000000001d30020000000000525250726f746563742bfb020000076f000000000000
	|HEAD_CRC:   0x43D2
	|HEAD_TYPE:  0x7A (RAR New-format subblock)
	|HEAD_FLAGS: 0xC000
	|   0x8000 LONG_BLOCK (ADD_SIZE field present)
	|   0x4000 SKIP_IF_UNKNOWN (older RAR versions will ignore this block)
	|   0x0000 LHD_WINDOW (Dictionary size 64 KiB)
	|HEAD_SIZE:  0x36 (54 bytes)
	+PACK_SIZE: 447502 bytes (ADD_SIZE field)
	+UNP_SIZE: 447502 bytes
	+HOST_OS: Windows used to create this file block.
	+FILE_CRC: 1A8B29CD
	+FTIME: 1980-00-00 00:00:00
	+UNP_VER: Version 2.9 is needed to extract.
	+METHOD: Storing
	+NAME_SIZE: always present
	+ATTR: 0
	+FILE_NAME: RR
	+RR: Recovery Record
	+Recovery sectors: 763
	+Data sectors: 28423
	+Protect+
	"""
#	print("Changes in the Recovery Record headers:")
#	print(r09bytes.encode('hex'))
#	print(r10bytes.encode('hex'))
#	print(r10bytes.encode('utf8'))
	
	# beforerr: all data, fixed, before the Recovery Record
	join_data(beforerr, hbeforefix, extract)
	# place where the RR stuff starts
	size = os.stat(beforerr).st_size
	
	# calculates + writes headers
	with open(beforerr, "r+b") as rarfs:
		rescene._write_recovery_record(r10block, rarfs) # appends the data

	# fix
	with open(beforerr, "rb") as gen:	
		gen.seek(size)
		hgenstuff = gen.read()
		
		# copy genned stuff and fix it
		# fix the block that is put before the recovery record (rrblock)
		with open(rrblock, "wb") as fixdata:
			fixdata.write(hgenstuff)
		
		gen.seek(0)
		crc_before = calc_crc(gen.read(size))
		print("all data before: %x" % crc_before)
		
	# calculate RR crc
	block = rar.RarNewSubBlock(hgenstuff, 0, rrblock)
	assert block.header_size+block.add_size == len(hgenstuff)
#	crc = calc_crc(hgenstuff[block.header_size:block.header_size+block.add_size])
##	print("%x" % ~crc)
	
	crc = calc_crc(hgenstuff[block.header_size:], ~0x0fffffff)
	
	
#	# I) try with a running crc -> NO
#	for b in rar.RarReader(r10).read_all():
#		if b.rawtype == rar.BlockType.RarPackedFile:
#			start = b.file_crc
#	crc = calc_crc(hgenstuff[-block.add_size:], 0xEDB88320)
#	print("%x" % (~crc & 0xffffffff)) 
	
#	print("size before: %d" % size)
#	print("header size: %d" % block.header_size)
#	print("add size: %d" % block.add_size)
#	assert size + block.header_size + block.add_size + 20 == 15000000
#	assert block.data_sectors*2 + block.recovery_sectors*512 == block.add_size
#	print("data sectors: %d" % block.data_sectors)
#	print("data sectors*2: %d" % (block.data_sectors*2))
#	# should be \xCD\x29\x8B\x1A hex(struct.unpack('<I', h)[0])
	
#	crc = calc_crc(hgenstuff[-block.add_size+(block.data_sectors*2):])
#	crc = calc_crc(hgenstuff[block.header_size:block.header_size+(block.data_sectors*2)])

	# III) try with additional 0 bytes added in between
	
#	if tofind == crc or tofind == (crc & 0xffffffff) or tofind == ~crc:
#		print("start: %d, end: %d" % (begin, end))
#		sys.exit() 
	
	# II) try different range -> NO
#	crc = zlib.adler32(hgenstuff[-block.add_size:])
##		for i in range(0, 55):
##			c = calc_crc(hgenstuff[-block.add_size-i:])
##			if c == 0x1a8b29cd:
##				print("FOUND!" + c)
#	if crc == 0x1a8b29cd:
#		print("FOUND!" + crc)
#	print("%x" % (~crc & 0xffffffff))
#	print("%x" % (crc & 0xffffffff))
#	print("%x" % ~crc)
#	print("%x" % crc)
	
	bytes = hgenstuff[:7+9] + struct.pack("<I", crc) + hgenstuff[7+9+4:]

	# header RR crc
	header_crc = zlib.crc32(bytes[2:block.header_size]) & 0xFFFF
	bytes = struct.pack("<H", header_crc) + bytes[2:] 
	with open(rrblock, "wb") as fixdata:
		fixdata.write(bytes)
		
	# to test if crc is wrong - also acd899e6
	with open(rrblock + "_onlyrr.bin", "wb") as fixdata:
		fixdata.write(hgenstuff[block.header_size:])
	
	
	
	# change the orig genned one
	with open(beforerr, "r+b") as gen:
		gen.seek(size)
		gen.write(bytes)
		
	print(bytes[:block.header_size].encode('hex'))

		
def create_result():
	create_after(beforerr)
	join_data(resultfull, beforerr, hafterfix)
			
#extract_part()
get_headers_r10()
fix_file_header()

calculate_recovery_record()
create_result()




#for block in rar.RarReader(dir + "empty.rar").read_all():
#	print(block.explain())

# CD 29 8B 1A

#for block in rar.RarReader(dir + "hashtest/10meg_1percent.rar").read_all():
#	print(block.explain())
#
#for block in rar.RarReader(dir + "hashtest/10meg_2percent.rar").read_all():
#	print(block.explain())

#d0a5bdcd empty20
#f121d696 empty
#https://docs.google.com/spreadsheet/ccc?key=0AhnMwEU5VWYudG5oYzB6OWVUQmJJOTNjX2JFZUlnWFE
