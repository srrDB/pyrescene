"""
0xD4 (212 bytes)
|Header bytes: 4a77740301560016f0fa020000605d032d44fd8f3793273f14302e00a401000000000000000000006d6f6465726e2e66616d696c792e7330326531312e31303830702e626c757261792e783236342d6269612e6d6b76
|HEAD_CRC:   0x774A
37 +
""" 
import zlib, struct
import sys
before = "C:/Users/Me/Desktop/before.bin"
after = "C:/Users/Me/Desktop/after.bin"
inbetween = "C:/Users/Me/Desktop/inbetween.bin"
#with open("C:/Users/Me/Desktop/modern.family.s02e11.1080p.bluray-bia.r27" , "rb") as rar:
#	with open(before, "wb") as b:
#		b.write(rar.read(0x14))
#	with open(inbetween, "wb") as inb:
#		inb.write(rar.read(86))
#	with open(after, "wb") as a:
#		a.write(rar.read())
with open(before, "rb") as b:
	bef = b.read()
with open(after, "rb") as a:
	aft = a.read()
with open(inbetween, "rb") as n:
	inb = n.read()
	
#print inb.encode('hex')
#print len(inb)
#sys.exit()
	
def fix_file_header(file_header, date_part):
	""" fix the headers before the data """
	# check if the provided file_headers integrity is correct
	assert struct.unpack("<H", file_header[:2])[0] == zlib.crc32(file_header[2:]) & 0xFFFF
	before = file_header[:7+9+4]
	after = file_header[7+9+4+1:]
	fixed_crc_header = before + struct.pack("c", chr(date_part)) + after
	header_crc = zlib.crc32(fixed_crc_header[2:]) & 0xFFFF
	fixed_crc_header = struct.pack("<H", header_crc) + fixed_crc_header[2:]
	
	assert struct.unpack("<H", fixed_crc_header[:2])[0] == zlib.crc32(fixed_crc_header[2:]) & 0xFFFF
	return fixed_crc_header
	
for i in range(0x37, 0x72):
#	crc = zlib.crc32(bef + struct.pack("c", "%X" % i) + aft)
	inb = fix_file_header(inb, i)
	crc = zlib.crc32(bef + inb + aft)
	print("%08X - fa6f96b5" % (crc & 0xffffffff))
	print crc, 0xfa6f96b5
	if crc == 0xfa6f96b5:
		print("found it: %d" % i)
		with open("C:/Users/Me/Desktop/good.bin", "wb") as good:
			good.write(bef + inb + aft)
		break
#	with open("C:/Users/Me/Desktop/good.bin", "wb") as good:
#		good.write(bef + hex(i) + aft)
#	break
with open("C:/Users/Me/Desktop/good.bin", "wb") as good:
	good.write(bef + inb + aft)
		

#with open("C:/Users/Me/Desktop/rebuild/good.bin", "rb") as good:
with open("C:/Users/Me/Desktop/modern.family.s02e11.1080p.bluray-bia.rar", "rb") as good:
	data = good.read()
	print "%s" % struct.pack('>I', zlib.crc32(data) & 0xffffffff).encode('hex')
	print "%X" % zlib.crc32(data)

print "echt: b94d4433, output: 71325EC3"