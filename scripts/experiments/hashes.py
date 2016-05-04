import os
import sys
import pprint
# for running the script directly from command line
sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)),
                            '..',))
from rescene.main import content_hash

path = "D:\srrdb.com_2011-10-27"
path = sys.argv[1]
# # cd1 before the RARs and CD1 before the SFVs
# bad = os.path.join(path, "007.A.View.To.A.Kill.1985.iNTERNAL.DVDRip.XviD-iNCiTE.srr")
# # Unicode comments in the SFV
# bad2 = os.path.join(path, "13.Going.On.30.DVDRiP.XviD-BRUTUS.srr")
# pprint.pprint(rescene.info(bad))
# pprint.pprint(rescene.info(bad2))
# print(rescene.hash_srr(bad))

print(len(os.listdir(path)))
for srr in os.listdir(path):
    try:
        release = srr[:-4]
        srr_file = os.path.join(path, srr)
        srr_hash = content_hash(srr_file)
        print(srr_hash + ";" + release)
    except KeyboardInterrupt:
        sys.exit()
    except BaseException as err:
        print(err)

# 3.On.Stage.Rest.Of.Pinkpop.2011.DUTCH.WS.PDTV.XviD-iFH
# (<type 'exceptions.EnvironmentError'>, EnvironmentError('Invalid RAR block length (20) at offset 0x1c528',), <traceback object at 0x032E5AA8>)
