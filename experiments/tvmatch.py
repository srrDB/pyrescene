import re
import unittest

def get_show_info(release_name):
	
	return re.match(fullPattern, release_name)

# we can detect miniseries

#(?(id/name)yes-pattern|no-pattern)

regular = ("[\.-]?((?<![a-zA-Z])[sS](?P<season>\d?\d)(?![\dxX])[\.]?|" # season: S2 or s02
		   "(?<![xX])[eE][pP]?(\d{1,3})|[eE][pP]?(\d{1,3})"		  # episode: e1, E02 or E112, Ep10, Ep9
		   "((\.[eE]|-?[eE]?)" # 24.S01E13.12.Noon-1PM.INTERNAL.DVDRip.XviD-RETRO; . sep
		   "\d{2,3})+)+") # double episode XXX: can it be 1#?

fov = ("\.?(?<!\d)(?P<fseason>\d{1,2})[x](?P<fepisode>\d{2,3})" # season/episode
	   "([\._-]((?P<feseason>\d{1,2})[x])?)?"
	   "(?P<feepisode>(?<![\.])\d{2,3})?[\._]?") # multiple episode

#retro = "\.[eE][pP](\d{2,3})" # Un.Gars.Une.Fille.Ep020.FRENCH.DVDRiP.XViD.INT-uGuF


iso8601 = ("((?P<year>(19|20)?\d\d)"
		   "(?P<sep>[-\.]?)" # separator
		   "(?P<month>0[1-9]|1[012])"
		   "(?P=sep)" # same separator; \n: nth group
		   "(?P<day>0[1-9]|[12][0-9]|3[01]))(?=.+(HDTV|PDTV|DSR|TVRip|dTV|SATRip).+)")

daterev = ("((?P<rday>0[1-9]|[12][0-9]|3[01])"
		   "(?P<pes>[-\.])"
		   "(?P<rmonth>0[1-9]|1[012])"
		   "(?P=pes)"
		   "(?P<ryear>(19|20)?\d\d))(?=.+(HDTV|PDTV|DSR|TVRip|dTV|SATRip).+)")

part = "((Part|Pt|PART)[\._-]?(?P<pepisode>\d{1,3}))[^\d]"

subpack = ("Season[._]?(?P<pseason>\d{1,2})(?!(\d|[._]\d{4}))")


patterns = [regular, fov, iso8601, daterev, part, subpack]

# if this one matches, it is a show
fullPattern = ""
for pattern in patterns:
	sep = "(.*" if fullPattern == "" else "|(.*"
	fullPattern += sep + pattern + ".*)"
print(fullPattern)

def is_show(release_name):
	return True and re.match(fullPattern, release_name)

matches = [
		 "Jay.Leno.2009.09.14.Jerry.Seinfeld.720p.HDTV.x264-MOMENTUM",
		 "Jay.Leno.2009-09-14.Jerry.Seinfeld.720p.HDTV.x264-MOMENTUM",
		 "Jay.Leno.20090914.Jerry.Seinfeld.720p.HDTV.x264-MOMENTUM",
		 "The.7pm.Project.2010.01.03.WS.PDTV.XviD-RTA",
		 "The.7pm.Project.2010-01-03.WS.PDTV.XviD-RTA",
		 "Boxing.A.Ward.vs.A.Green.20100616.PDTV.XviD-MaM",
		 
		 "24.S07E24.PREAIR.DVDRip.XviD-TOPAZ",
		 "24.S7E24.PREAIR.DVDRip.XviD-TOPAZ",
		 "24.S7E124.PREAIR.DVDRip.XviD-TOPAZ",
		 "24.S7.E124.PREAIR.DVDRip.XviD-TOPAZ",
		 "24.S7.E1.PREAIR.DVDRip.XviD-TOPAZ",
		 "Friends.S10E01.UNCUT.DVDRip.XviD-SiSO"
		 "24.1x01.12.00.AM_1.00.AM.AC3.iNTERNAL.DVDRip_WS_XviD-FoV",
		 "Above.Suspicion.Part2.HDTV.XviD-BiA",
		 "Above.Suspicion.Pt2.HDTV.XviD-BiA",
		 "Above.Suspicion.Part.2.HDTV.XviD-BiA",
		 "Above.Suspicion.Part.22.HDTV.XviD-BiA",
		 "Above.Suspicion.Part.222.HDTV.XviD-BiA",
		 "Above.Suspicion.Part_2.HDTV.XviD-BiA",
		 "Archangel.2005.PART2.DVDRip.XviD-MEDiAMANiACS",
		 "All.Dogs.Go.To.Heaven.Part1.1989.720p.BluRay.x264-HALCYON",
		 "24.S01E13.12.Noon-1PM.INTERNAL.DVDRip.XviD-RETRO",
		 "Un.Gars.Une.Fille.Ep020.FRENCH.DVDRiP.XViD.INT-uGuF",
		 "Kaamelott.S01EP100.FiNAL.FRENCH.DVDRiP.XViD-CRiMETiME",
		 "Slings.and.Arrows.S03.EXTRAS.DVDRip.XviD-NODLABS",
		 "Spots.Bumber.Adventure.Pack.E09.Spots.Tent.DVDRip.XViD-SPRiNTER",
		 "Warehouse.13.S03E11-E12.Emily.Lake-Stand.HDTV.XviD-FQM",
		 "Twilight.Zone.80s.S01E39-E40-E41.DVDRip.XviD-FFNDVD",
		 "The.A-Team.S03E02.E03.DVDRip.XviD-iNFiNiTE",
		 "Eureka.S01E01.E02.720p.HDTV.x264-hV",
		 "Doctor.Who.2005.Ep9.WS.DVDRip.XviD-m00tv",
		 "The.Singing.Detective.1986.Ep1.Skin.DVDRip.XviD-FRAGMENT",
		 "Doctor.Who.2005.Ep10.WS.DVDRip.XviD-m00tv",
		 "Trial.and.Retribution.S01E0102.DVDRip.XviD-iMMORTALs",
		 "24.1x24.11.00.PM_12.00.AM.AC3.DVDRip_WS_XviD-FoV",
		 "The.Ultimate.Fighter.S14E01-02.HDTV.XviD-aAF",
		 "Samurai.Girl.S01E01-E02.720p.HDTV.x264-CTU",
		 "Firefly.S01E01-02.720p.BluRay.x264-REAVERS",
		 "FireFly.S01E01-02.1080p.BluRay.x264-REAVERS",
		 "The.4400.S03E01-02.DVDRip.XviD-TOPAZ.",
		 "GSL.Global.StarCraft.II.League.2011.03.03.Season.5.Code.S.Ro16.Day.1.WEBRiP.XviD-W4F",
		 "Buffy.Season6.Extras.DVDRip_XviD-FoV",
		 "Ax.Men.S02.Road.To.Season.2.Special.DVDRip.XviD-WiDE",
		 "30.Rock.S04E01.Season.4.HDTV.XviD-FQM",
		 "Ice.Road.Truckers.S02.Bonus.Off.The.Ice.Season.2.DVDRip.XviD-RiTALiN",
		 "Scrubs.Season.2.Extras.DVDRip.XviD-CRT",
		 "Top.Gear.The.Best.Of.Season.1.and.2.REPACK.DVDRip.XviD-EPiSODE",
		 "XIII.2008.Miniseries.Part.1.DVDRip.XviD-aAF",
		 "Wuthering.Heights.Part.1.2009.STV.720p.Bluray.x264-hV",
		 
		 ]

nomatch = [
		   "Matrix.1999.German.DL.1080p.BluRay.x264.iNTERNAL-DARM",
		   "Matrix.Reloaded.Extras.2003.XviDVD-TmN",
		   "The.Matrix.1999.1080p.BluRay.MULTiSUBS.iNT.x264-GRiMRPR",
		   "The.Animatrix.2003.720p.BluRay.x264-HANGOVER",
		   "Friends.S10xE01.UNCUT.DVDRip",
		   "Drawing.Clipart.2000.DVDR...",
		   "24.1X01.AC3.iNTERNAL.DVDRip_WS_XviD-FoV", # yes/no?
		   "The.Mean.Season.1985.DVDRip.XviD-VH-PROD",
		   "Intercontinental.Le.Mans.Cup.2011.Silverstone.00.48-00.00.720p.HDTV.x264-WHEELS",
		   "Open.Season.2.2008.FLEMiSH.STV.DVDRip.XviD-CaRRe",
		   "The.Final.Season.2007.DVDRip.XviD-FLAiTE",
		   "W.2008.720p.BluRay.x264-AVS720",
		   "Taiheiyou_no_Arashi_JPN_PS3-HR",
		   "NBA_2K12_PAL_PS2DVD-2CH",
		   "Flo_Rida_and_Juliet_Simms-Medley_(The_Voice_2012-05-08)-720p-x264-2012-SRPx",
		   "Gameloft.Littles.Pet.Shop.v1.2.4.128x128.J2ME.Retail-MSGPDA",
		   ]
# should not match; false positive, sees date
# "24.1X01.12.00.AM_1.00.AM.AC3.iNTERNAL.DVDRip_WS_XviD-FoV",


	
print("Done!")

""" original one Skalman^:
if(preg_match("/(e[0-9][0-9])|(s[0-9][0-9])|([0-9][0-9]x[0-9][0-9])|
([0-9]x[0-9][0-9])|(part[0-9])|(part\-[0-9])|(part\.[0-9])/i", 
strtolower($filename))) {
"""

class TestAll(unittest.TestCase):
	def test_all(self):
		for rel in matches:
			m = re.match(fullPattern, rel)
			print(rel)
			assert m is not None
		#	print(m.groups())
			print(m.groupdict())
		
		for rel in nomatch:
			m = re.match(fullPattern, rel)
			print(rel)
			if m:
				print(m.groups())
			assert m is None
			
	def test_date(self):
				
		r = get_show_info("mlqksdjf")
		
		
		
# when this file is not imported, but ran directly
if __name__ == '__main__':
	suites = list()
	suites.append(unittest.TestLoader().loadTestsFromTestCase(TestAll))
	alltests = unittest.TestSuite(suites)
	
	unittest.TextTestRunner(verbosity=2).run(alltests)
