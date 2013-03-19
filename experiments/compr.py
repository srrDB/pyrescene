import os
import subprocess
import sys
import pprint
import rescene.comprrar as rb

dict_size = {
	64 : "-mda",
	128: "-mdb", 
	256: "-mdc", 
	512: "-mdd",
	1024: "-mde", 
	2048: "-mdf",
	4096: "-mdg",
}
			
def generate_testfiles(rarbindir, raroutdir):
	rb.initialize_rar_repository(rarbindir)
	for rarbin in rb.repository.get_rar_executables("2020-01-01"):
		files = ["D:\\test\\dead_like_me.1x14.rest_in_peace.ws_dvdrip_xvid-sample-fov.avi"]
		for i in range(5):
			# -s: solid archive
			
			rarname = "".join([str(rarbin), " m", str(i+1), ".rar"])
			rarname = os.path.join(raroutdir, rarname)
			
			args = [rarbin.path(), "a", "-m" + str(i+1), dict_size[4096], rarname] + [files]   
			create = subprocess.Popen(args)
			create.wait()
			#create = custom_popen(args)

def compare(raroutdir):
	# for each compression method dict with all versions
	files = [""] * 5
	for i in range(len(files)):
		files[i] = dict()
		
	for fname in os.listdir(raroutdir):
		(files[int(fname[-5:-4])-1])[fname[:10]] = fname
	pprint.pprint(files)
	f1 = f2 = 0
	for i in range(len(files)):
#		print sorted(files[i-1].items())
#		continue
		for k, v in sorted(files[i].items()):
			if not f1:
				f1 = v
				continue
			f2 = v
			if _do_cmp(os.path.join(raroutdir, f1), 
					   os.path.join(raroutdir, f2)):
				print "SAME:", k, f1, f2
			else:
				print "DIFF:", k, f1, f2
			f1 = f2

def _do_cmp(f1, f2):
	bufsize = 8*1024
	with open(f1, 'rb') as fp1:
		with open(f2, 'rb') as fp2:
			while True:
				b1 = fp1.read(bufsize)
				b2 = fp2.read(bufsize)
				if b1 != b2:
					return False
				if not b1:
					return True
			
# disconnect cmd from parent fds, _read only from stdout
def custom_popen(cmd):
	# needed for py2exe
	creationflags = 0
	if sys.platform == 'win32':
		creationflags = 0x08000000 # CREATE_NO_WINDOW

	# 3xPIPE seems unreliable, at least on osx
	try:
		null = open(os.devnull, "wb")
		_in = null
		_err = null
	except IOError:
		_in = subprocess.PIPE
		_err = subprocess.STDOUT

	# run command
	return subprocess.Popen(cmd, stdout=subprocess.PIPE, 
							stdin=_in, stderr=_err, 
							creationflags=creationflags)

#generate_testfiles("Z:\\rar\\_winbin", "D:\\test")
compare("D:\\test")


