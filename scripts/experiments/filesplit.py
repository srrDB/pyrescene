import os, sys

# Author: YopoM

#-----------------------------------------------------------------------------

def progdisp():
	print("Module %s\nSplit a file into 2 pieces starting at a specified position.\n" % sys.argv[0])

#-----------------------------------------------------------------------------

def progusage():
	print("Usage:\nThe output is always written to the 2 files SPLIT1.OUT and SPLIT2.OUT")
	print("Any existing files with those names are overwritten");
	print("The input file is left untouched")
	print("Usage: Filesplt.py Fname startat")
	print("  Fname is filename to split")
	print("  startat is postition to start split at")

#-----------------------------------------------------------------------------

def is_number(s):
	try:
		float(s)
		return True
	except ValueError:
		return False

#-----------------------------------------------------------------------------

def RdInp_WrOutp(TotBytesToWrite, Ifile, OfileName):
	RdSize = 8192
	BytesToWrite = TotBytesToWrite
	Ofile = open(OfileName, "wb", 0)
	while(BytesToWrite):
		if (BytesToWrite < RdSize):
			n = BytesToWrite
		else:
			n = RdSize
		buff = Ifile.read(n)
		Ofile.write(buff)
		BytesToWrite = BytesToWrite - n
	Ofile.close

#-----------------------------------------------------------------------------

def doit(inpfile, splitat):
	if not os.path.isfile(inpfile):
		print("Error: Input file %s does not exist, aborting!" % inpfile)
		sys.exit(2)

	if not is_number(splitat):
		print("Error: size parameter not numeric, aborting!")
		sys.exit(3)

	Nsplitat = int(splitat)
	if (Nsplitat < 1):
		print("Error: size parameter must be > 0, aborting!")
		sys.exit(4)

	print("Splitting file %s at position %d" % (inpfile, Nsplitat))
	f = open(inpfile, "rb", 0)

	f.seek(0, 2)  # seek to EOF
	siz = f.tell()  # get length
	f.seek(0, 0)  # reset to beginning of file

	if (Nsplitat > siz):
		print("Error: input file smaller than specified split at position!")
		sys.exit(5)

	RdInp_WrOutp(Nsplitat, f, "SPLIT1.OUT")
	RdInp_WrOutp(siz - Nsplitat, f, "SPLIT2.OUT")
	f.close

#-----------------------------------------------------------------------------

def start():
	progdisp()
	if len(sys.argv) < 3:
		print("\nError: Insufficient number of arguments")
		progusage()
		sys.exit(1)
	# below requires python 2.6 or higher
	# print("Args: {0} ... {1}" .format(sys.argv[1],sys.argv[2]))
	doit(sys.argv[1], sys.argv[2])

#-----------------------------------------------------------------------------

if __name__ == "__main__":
	start()
