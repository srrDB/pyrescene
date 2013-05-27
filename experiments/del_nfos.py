# Deletes a lot of badly named nfo files

import rescene

srr = "Beauty.and.the.Beast.2012.S01E02.720p.HDTV.x264-IMMERSE.srr"
good = "beauty.and.the.beast.2012.s01e02.720p.hdtv.x264-immerse.nfo"

i = rescene.info(srr)
i["stored_files"].pop(good)
for sfile in  i["stored_files"].keys():
	if not sfile.endswith(".nfo"):
		i["stored_files"].pop(sfile)
rescene.remove_stored_files(srr, i["stored_files"])
print("Done!")