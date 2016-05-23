import rescene
import os
import glob

dir = "D:/srrdb.com_2011-10-27/new/"

for file in glob.glob(dir + "*.srr"):
	print("Reading %s" % file)
	try:
		rescene.info(os.path.join(dir, file))
	except EnvironmentError as e:
		print(e)
		os.rename(os.path.join(dir, file), os.path.join(dir, "incomplete", file))
# 	except:
# 		pass
