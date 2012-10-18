import rescene
import os

folder = "D:/srrdb/bbachive_srrs/srrs0d-150d/iffy/good"

for srr_file in os.listdir(folder):
	srrf = os.path.join(folder, srr_file)
	sf = rescene.info(srrf)['stored_files']
	for sfile in sf:
		if sf[sfile].file_size == 592451 and sf[sfile].file_name[-4:] == ".png":
			print sf[sfile].file_name
			rescene.remove_stored_files(srrf, sf[sfile].file_name)
			break