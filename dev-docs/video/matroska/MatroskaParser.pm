#             This work is hereby released into the Public Domain.
#               To view a copy of the public domain dedication,
#           visit http://creativecommons.org/licenses/publicdomain/
#                             or send a letter to
#                      Creative Commons,
#                      559 Nathan Abbott Way
#                      Stanford, California 94305, USA.
#
################################################################################
#
# To use:
# use MatroskaParser;
# $file = new matroska('filename');
# $structure = $file->parse();
#
# parse() may take an optional element which is a hash of tags to override handling of.
#   parse({'Segment' => 0}) will skip any 'Segment' tags found, and place 'SKIPPED' in the 'value' key.
#   parse({'Block' => 1}) will read blocks (they are by default skipped)
#   parse({'Cluster' => 2}) will read clusters and everything within a cluster.
#   parse({'EBML' => 0, 'Segment' => 2}) will skip the EBML elements, but read everything in the 'Segment' elements
# A list of valid element names is in the "$matroska::Elements" hash in this file
# Also, the default handling of each element is in the 'transverse' key of each element.
#
# All the data in the "$matroska::Elements" hash was gathered from http://www.matroska.org/technical/specs/
#
# $file->parse() will give you a variable that looks like this:
# --HASH--
#   'EBML'>   --ARRAY--
#     0:  --HASH--
#       'headersize'> 5
#       'pos'>    0
#       'size'>   19
#       'children'> --HASH--
#         'DocType'> --HASH--
#           'headersize'> 3
#           'pos'>    5
#           'size'>   8
#           'value'>  'matroska'
#         'DocTypeReadVersion'> --HASH--
#           'headersize'> 3
#           'pos'>    20
#           'size'>   1
#           'value'>  1
#         'DocTypeVersion'> --HASH--
#           'headersize'> 3
#           'pos'>    16
#           'size'>   1
#           'value'>  1
#   'Segment'> --ARRAY--
#     0:  --HASH--
#       'headersize'> 12
#       'pos'>    24
#       'size'>   4908505
#       'children'> --HASH--
#         'Cluster'> --ARRAY--
#           0:  --HASH--
#             'headersize'> 7
#             'pos'>    5378
#             'size'>   18728
#             'value'>  'SKIPPED'
#           1:  --HASH--
#             'headersize'> 7
#             'pos'>    24113
#             'size'>   20471
#             'value'>  'SKIPPED'
# etc.
# 
# So to get the DocType, use $a->{'EBML'}[0]{'children'}{'DocType'}{'value'}
# To get the position of the DocTypeVersion, use $a->{'EBML'}[0]{'children'}{'DocTypeVersion'}{'pos'}
# 
# Elements which can have multiple entries are in an array, so the first cluster is {'Cluster'}[0], second is {'Cluster'}[1], etc.
# Elements which can not have multiple entries have no array, so the doctype is just {'DocType'}.
# Each element has a 'pos', 'size', and 'headersize' key. These are the position in the file,
# the size of the inner contents (ie. minus the header), and the size of the header.
# So to go to the end of an element, seek to 'pos' + 'headersize' + 'size'.
#
# Blocks (if parsed) have the following structure:
# 'Block'>  --HASH--
#   'headersize'> 3
#   'pos'>    5391
#   'size'>   1626
#   'children'> --HASH--
#     'lacing'> 'EBML'
#    ('framesize') <-- Only for 'lacing' == 'Fixed'
#    ('gap'> 1)       <-- Only if the 'gap' flag is set (see Matroska specs for more info)
#     'timecode'> 0
#     'track'>  1
#     'frames'> --ARRAY--
#       0:  --HASH--
#         'pos'>    5408
#         'size'>   28
#       1:  --HASH--
#         'pos'>    5436
#         'size'>   22
#       2:  --HASH--
#         'pos'>    5458
#         'size'>   22
#       3:  --HASH--
#         'pos'>    5480
#         'size'>   22
#       4:  --HASH--
#         'pos'>    5502
#         'size'>   332
#       5:  --HASH--
#         'pos'>    5834
#         'size'>   295
#       6:  --HASH--
#         'pos'>    6129
#         'size'>   416
#       7:  --HASH--
#         'pos'>    6545
#         'size'>   475
#
# No-lacing looks like:
# 'Block'>  --HASH--
#   'children'> --HASH--
#     'lacing'> 'None'
#     'timecode'> 1567
#     'track'>  1
#     'frames'> --ARRAY--
#       0:  --HASH--
#         'pos'>    15505
#         'size'>   1951
#
# Note that 'lacing' must be one of 'None', 'Xiph', 'EBML', 'Fixed'
# 
# # Example:
# 
# use MatroskaParser;
# 
# $filename = 'path/to/matroska.mkv';
# $file = new matroska($filename);
# 
# # Standard parsing (don't go into clusters, seek entries, etc.
# $std = $file->parse();
# 
# # Parse the entire EBML elements, but no Segment elements
# $onlyEBML = $file->parse({'EBML' => 2, 'Segment' => 0});
# 
# $onlyEBML:
# --HASH--
#   'EBML'>   --ARRAY--
#     0:  --HASH--
#       'children'> --HASH--
#         'DocType'> --HASH--
#           'headersize'> 3
#           'pos'>    5
#           'size'>   8
#           'value'>  'matroska'
#         'DocTypeReadVersion'> --HASH--
#           'headersize'> 3
#           'pos'>    20
#           'size'>   1
#           'value'>  1
#         'DocTypeVersion'> --HASH--
#           'headersize'> 3
#           'pos'>    16
#           'size'>   1
#           'value'>  1
#       'headersize'> 5
#       'pos'>    0
#       'size'>   19
#   'Segment'> --ARRAY--
#     0:  --HASH--
#       'headersize'> 12
#       'pos'>    24
#       'size'>   4908505
#       'value'>  'SKIPPED'
# (That's the entire thing)
#
################################################################################
#
# Questions, comments, and bugs can be emailed to "rswilson at ucsc dot edu".
#
# KNOWN PROBLEMS:
#
# * It's not astoundingly fast. This is partially because it's Perl, but
#     partially because I don't use the seektables. I'll probably add that later.
#
# * Dates are interpreted as integers (=nanoseconds since millenium).
#
# * All integers are treated as unsigned. This is because I'm lazy.
#
# * A broken file will result in several warning messages, followed by complete
#     and utter death.
#
# * I don't know if it will handle files > 4GB correctly. I think Perl uses
#     floats for integers that are too big, so the seeking might not work, which
#     would result in strange errors and eventual termination (see previous).
#
# * I've only tested it on my Windows XP machine, but it should work just fine
#     on Linux, etc.. HOWEVER, reading floats will break on a little-endian
#     machine.
#
# * Easy-to-parse binary data (like 4CC codes and SeekID entries) are simply
#     treated as binary. Blocks, however, are parsed to the frame level.
#
################################################################################
#
# CHANGELOG:
# 0.1
#   First released into the wild. Rampant bugs and programmer hacks predominate.
#
################################################################################
package matroska;
################################################################################
use strict;
use constant {
	SINT => 0,
	UINT => 1,
	FLOAT => 2,
	STRING => 3,
	UTF8 => 4,
	DATE => 5,
	ELEMENT => 6,
	BINARY => 7,
	BLOCK => 8,

	SINGLE => 1,
	MULTI => 0,
};

use Math::BigInt;

BEGIN {
	$matroska::DefaultBuffer = 65536;
	$matroska::FlushBuffer = 65536;
	$matroska::UseSeekInfo = 0;			# This currently does not work. Seek info is never used.

	$matroska::Elements = {

	# Dummy parent
		'' => {'name' => 'FILE', 'value' => ELEMENT, 'multi' => 0, 'traverse' => 1, 'pos' => {}},
	
	# EBML Basics
		0x0A45DFA3	=> {'name' => 'EBML',				'value' => ELEMENT,	'multi' => 1, 'traverse' => 1, 'pos' => {'' => 1}},
		0x0286		=> {'name' => 'EBMLVersion',		'value' => UINT,	'multi' => 0, 'traverse' => 1, 'pos' => {0x0A45DFA3 => 1}},
		0x02F7		=> {'name' => 'EBMLReadVersion',	'value' => UINT,	'multi' => 0, 'traverse' => 1, 'pos' => {0x0A45DFA3 => 1}},
		0x02F2		=> {'name' => 'EBMLMaxIDLength',	'value' => UINT,	'multi' => 0, 'traverse' => 1, 'pos' => {0x0A45DFA3 => 1}},
		0x02F3		=> {'name' => 'EBMLMaxSizeLength',	'value' => UINT,	'multi' => 0, 'traverse' => 1, 'pos' => {0x0A45DFA3 => 1}},
		0x0282		=> {'name' => 'DocType',			'value' => STRING,	'multi' => 0, 'traverse' => 1, 'pos' => {0x0A45DFA3 => 1}},
		0x0287		=> {'name' => 'DocTypeVersion',		'value' => UINT,	'multi' => 0, 'traverse' => 1, 'pos' => {0x0A45DFA3 => 1}},
		0x0285		=> {'name' => 'DocTypeReadVersion',	'value' => UINT,	'multi' => 0, 'traverse' => 1, 'pos' => {0x0A45DFA3 => 1}},
	# Global
		0x3F		=> {'name' => 'CRC-32',				'value' => BINARY,	'multi' => 1, 'traverse' => 0, 'pos' => {'all' => 1}},
		0x6C		=> {'name' => 'Void',				'value' => BINARY,	'multi' => 1, 'traverse' => 0, 'pos' => {'all' => 1}},
	# Segment
		0x08538067	=> {'name' => 'Segment',			'value' => ELEMENT,	'multi' => 1, 'traverse' => 1, 'pos' => {'' => 1}},
	# Meta-seek
		0x014D9B74	=> {'name' => 'SeekHead',			'value' => ELEMENT,	'multi' => 1, 'traverse' => 1, 'pos' => {0x08538067 => 1}},
		0x0DBB		=> {'name' => 'Seek',				'value' => ELEMENT,	'multi' => 1, 'traverse' => 0, 'pos' => {0x014D9B74 => 1}},
		0x13AB		=> {'name' => 'SeekID',				'value' => BINARY,	'multi' => 0, 'traverse' => 1, 'pos' => {0x0DBB => 1}},
		0x13AC		=> {'name' => 'SeekPosition',		'value' => UINT,	'multi' => 0, 'traverse' => 1, 'pos' => {0x0DBB => 1}},
	# Segment Information
		0x0549A966	=> {'name' => 'Info',				'value' => ELEMENT,	'multi' => 1, 'traverse' => 1, 'pos' => {0x08538067 => 1}},
		0x33A4		=> {'name' => 'SegmentUID',			'value' => BINARY,	'multi' => 0, 'traverse' => 0, 'pos' => {0x0549A966 => 1}},
		0x3384		=> {'name' => 'SegmentFilename',	'value' => UTF8,	'multi' => 0, 'traverse' => 1, 'pos' => {0x0549A966 => 1}},
		0x1CB923	=> {'name' => 'PrevUID',			'value' => BINARY,	'multi' => 0, 'traverse' => 0, 'pos' => {0x0549A966 => 1}},
		0x1C83AB	=> {'name' => 'PrevFilename',		'value' => UTF8,	'multi' => 0, 'traverse' => 1, 'pos' => {0x0549A966 => 1}},
		0x1EB923	=> {'name' => 'NextUID',			'value' => BINARY,	'multi' => 0, 'traverse' => 0, 'pos' => {0x0549A966 => 1}},
		0x1E83BB	=> {'name' => 'NextFilename',		'value' => UTF8,	'multi' => 0, 'traverse' => 1, 'pos' => {0x0549A966 => 1}},
		0x0AD7B1	=> {'name' => 'TimecodeScale',		'value' => UINT,	'multi' => 0, 'traverse' => 1, 'pos' => {0x0549A966 => 1}},
		0x0489		=> {'name' => 'Duration',			'value' => FLOAT,	'multi' => 0, 'traverse' => 1, 'pos' => {0x0549A966 => 1}},
		0x0461		=> {'name' => 'DateUTC',			'value' => DATE,	'multi' => 0, 'traverse' => 1, 'pos' => {0x0549A966 => 1}},
		0x3BA9		=> {'name' => 'Title',				'value' => UTF8,	'multi' => 0, 'traverse' => 1, 'pos' => {0x0549A966 => 1}},
		0x0D80		=> {'name' => 'MuxingApp',			'value' => UTF8,	'multi' => 0, 'traverse' => 1, 'pos' => {0x0549A966 => 1}},
		0x1741		=> {'name' => 'WritingApp',			'value' => UTF8,	'multi' => 0, 'traverse' => 1, 'pos' => {0x0549A966 => 1}},
	# Cluster
		0x0F43B675	=> {'name' => 'Cluster',			'value' => ELEMENT,	'multi' => 1, 'traverse' => 0, 'pos' => {0x08538067 => 1}},
		0x67		=> {'name' => 'Timecode',			'value' => UINT,	'multi' => 0, 'traverse' => 1, 'pos' => {0x0F43B675 => 1}},
		0x27		=> {'name' => 'Position',			'value' => UINT,	'multi' => 0, 'traverse' => 1, 'pos' => {0x0F43B675 => 1}},
		0x2B		=> {'name' => 'PrevSize',			'value' => UINT,	'multi' => 0, 'traverse' => 1, 'pos' => {0x0F43B675 => 1}},
		0x20		=> {'name' => 'BlockGroup',			'value' => ELEMENT,	'multi' => 1, 'traverse' => 0, 'pos' => {0x0F43B675 => 1}},
		0x21		=> {'name' => 'Block',				'value' => BLOCK,	'multi' => 0, 'traverse' => 0, 'pos' => {0x20 => 1}},
		0x22		=> {'name' => 'BlockVirtual',		'value' => BINARY,	'multi' => 1, 'traverse' => 0, 'pos' => {0x20 => 1}},
		0x35A1		=> {'name' => 'BlockAdditions',		'value' => ELEMENT,	'multi' => 0, 'traverse' => 0, 'pos' => {0x20 => 1}},
		0x26		=> {'name' => 'BlockMore',			'value' => ELEMENT,	'multi' => 1, 'traverse' => 0, 'pos' => {0x35A1 => 1}},
		0x5E		=> {'name' => 'BlockAddID',			'value' => UINT,	'multi' => 0, 'traverse' => 0, 'pos' => {0x26 => 1}},
		0x25		=> {'name' => 'BlockAdditional',	'value' => BINARY,	'multi' => 0, 'traverse' => 0, 'pos' => {0x26 => 1}},
		0x1B		=> {'name' => 'BlockDuration',		'value' => UINT,	'multi' => 0, 'traverse' => 0, 'pos' => {0x20 => 1}},
		0x7A		=> {'name' => 'ReferencePriority',	'value' => UINT,	'multi' => 0, 'traverse' => 0, 'pos' => {0x20 => 1}},
		0x7B		=> {'name' => 'ReferenceBlock',		'value' => SINT,	'multi' => 1, 'traverse' => 0, 'pos' => {0x20 => 1}},
		0x7D		=> {'name' => 'ReferenceVirtual',	'value' => SINT,	'multi' => 0, 'traverse' => 0, 'pos' => {0x20 => 1}},
		0x24		=> {'name' => 'CodecState',			'value' => BINARY,	'multi' => 0, 'traverse' => 0, 'pos' => {0x20 => 1}},
		0x0E		=> {'name' => 'Slices',				'value' => ELEMENT,	'multi' => 1, 'traverse' => 0, 'pos' => {0x20 => 1}},
		0x68		=> {'name' => 'TimeSlice',			'value' => ELEMENT,	'multi' => 1, 'traverse' => 0, 'pos' => {0x0E => 1}},
		0x4C		=> {'name' => 'LaceNumber-DEAD',	'value' => UINT,	'multi' => 0, 'traverse' => 0, 'pos' => {0x68 => 1}},
		0x4D		=> {'name' => 'FrameNumber',		'value' => UINT,	'multi' => 0, 'traverse' => 1, 'pos' => {0x68 => 1}},
		0x4B		=> {'name' => 'BlockAdditionID',	'value' => UINT,	'multi' => 0, 'traverse' => 0, 'pos' => {0x68 => 1}},
		0x4E		=> {'name' => 'Delay',				'value' => UINT,	'multi' => 0, 'traverse' => 0, 'pos' => {0x68 => 1}},
		0x4F		=> {'name' => 'Duration',			'value' => UINT,	'multi' => 0, 'traverse' => 0, 'pos' => {0x68 => 1}},
	# Track
		0x0654AE6B	=> {'name' => 'Tracks',				'value' => ELEMENT,	'multi' => 1, 'traverse' => 1, 'pos' => {0x08538067 => 1}},
		0x2E		=> {'name' => 'TrackEntry',			'value' => ELEMENT,	'multi' => 1, 'traverse' => 1, 'pos' => {0x0654AE6B => 1}},
		0x57		=> {'name' => 'TrackNumber',		'value' => UINT,	'multi' => 0, 'traverse' => 1, 'pos' => {0x2E => 1}},
		0x33C5		=> {'name' => 'TrackUID',			'value' => UINT,	'multi' => 0, 'traverse' => 1, 'pos' => {0x2E => 1}},
		0x03		=> {'name' => 'TrackType',			'value' => UINT,	'multi' => 0, 'traverse' => 1, 'pos' => {0x2E => 1}},
		0x29		=> {'name' => 'FlagEnabled',		'value' => UINT,	'multi' => 0, 'traverse' => 1, 'pos' => {0x2E => 1}},
		0x08		=> {'name' => 'FlagDefault',		'value' => UINT,	'multi' => 0, 'traverse' => 1, 'pos' => {0x2E => 1}},
		0x1C		=> {'name' => 'FlagLacing',			'value' => UINT,	'multi' => 0, 'traverse' => 1, 'pos' => {0x2E => 1}},
		0x2DE7		=> {'name' => 'MinCache',			'value' => UINT,	'multi' => 0, 'traverse' => 1, 'pos' => {0x2E => 1}},
		0x2DF8		=> {'name' => 'MaxCache',			'value' => UINT,	'multi' => 0, 'traverse' => 1, 'pos' => {0x2E => 1}},
		0x03E383	=> {'name' => 'DefaultDuration',	'value' => UINT,	'multi' => 0, 'traverse' => 1, 'pos' => {0x2E => 1}},
		0x03314F	=> {'name' => 'TrackTimecodeScale',	'value' => FLOAT,	'multi' => 0, 'traverse' => 1, 'pos' => {0x2E => 1}},
		0x137F		=> {'name' => 'TrackOffset',		'value' => SINT,	'multi' => 0, 'traverse' => 0, 'pos' => {0x2E => 1}},
		0x136E		=> {'name' => 'Name',				'value' => UTF8,	'multi' => 0, 'traverse' => 1, 'pos' => {0x2E => 1}},
		0x02B59C	=> {'name' => 'Language',			'value' => STRING,	'multi' => 0, 'traverse' => 1, 'pos' => {0x2E => 1}},
		0x06		=> {'name' => 'CodecID',			'value' => STRING,	'multi' => 0, 'traverse' => 1, 'pos' => {0x2E => 1}},
		0x23A2		=> {'name' => 'CodecPrivate',		'value' => BINARY,	'multi' => 0, 'traverse' => 1, 'pos' => {0x2E => 1}},
		0x058688	=> {'name' => 'CodecName',			'value' => UTF8,	'multi' => 0, 'traverse' => 1, 'pos' => {0x2E => 1}},
		0x1A9697	=> {'name' => 'CodecSettings',		'value' => UTF8,	'multi' => 0, 'traverse' => 0, 'pos' => {0x2E => 1}},
		0x1B4040	=> {'name' => 'CodecInfoURL',		'value' => STRING,	'multi' => 1, 'traverse' => 0, 'pos' => {0x2E => 1}},
		0x06B240	=> {'name' => 'CodecDownloadURL',	'value' => STRING,	'multi' => 1, 'traverse' => 0, 'pos' => {0x2E => 1}},
		0x2A		=> {'name' => 'CodecDecodeAll',		'value' => UINT,	'multi' => 0, 'traverse' => 0, 'pos' => {0x2E => 1}},
		0x2FAB		=> {'name' => 'TrackOverlay',		'value' => UINT,	'multi' => 0, 'traverse' => 0, 'pos' => {0x2E => 1}},
		# Video
		0x60		=> {'name' => 'Video',				'value' => ELEMENT,	'multi' => 0, 'traverse' => 1, 'pos' => {0x2E => 1}},
		0x1A		=> {'name' => 'FlagInterlaced',		'value' => UINT,	'multi' => 0, 'traverse' => 1, 'pos' => {0x60 => 1}},
		0x13B8		=> {'name' => 'StereoMode',			'value' => UINT,	'multi' => 0, 'traverse' => 1, 'pos' => {0x60 => 1}},
		0x30		=> {'name' => 'PixelWidth',			'value' => UINT,	'multi' => 0, 'traverse' => 1, 'pos' => {0x60 => 1}},
		0x3A		=> {'name' => 'PixelHeight',		'value' => UINT,	'multi' => 0, 'traverse' => 1, 'pos' => {0x60 => 1}},
		0x14B0		=> {'name' => 'DisplayWidth',		'value' => UINT,	'multi' => 0, 'traverse' => 1, 'pos' => {0x60 => 1}},
		0x14BA		=> {'name' => 'DisplayHeight',		'value' => UINT,	'multi' => 0, 'traverse' => 1, 'pos' => {0x60 => 1}},
		0x14B2		=> {'name' => 'DisplayUnit',		'value' => UINT,	'multi' => 0, 'traverse' => 1, 'pos' => {0x60 => 1}},
		0x14B3		=> {'name' => 'AspectRatioType',	'value' => UINT,	'multi' => 0, 'traverse' => 1, 'pos' => {0x60 => 1}},
		0x0EB524	=> {'name' => 'ColorSpace',			'value' => BINARY,	'multi' => 0, 'traverse' => 1, 'pos' => {0x60 => 1}},
		0x0FB523	=> {'name' => 'GammaValue',			'value' => FLOAT,	'multi' => 0, 'traverse' => 1, 'pos' => {0x60 => 1}},
		# Audio
		0x61		=> {'name' => 'Audio',				'value' => ELEMENT,	'multi' => 0, 'traverse' => 1, 'pos' => {0x2E => 1}},
		0x35		=> {'name' => 'SamplingFrequency',	'value' => UINT,	'multi' => 0, 'traverse' => 1, 'pos' => {0x61 => 1}},
		0x38B5		=> {'name' => 'OutputSamplingFrequency','value' => UINT,'multi' => 0, 'traverse' => 1, 'pos' => {0x61 => 1}},
		0x1F		=> {'name' => 'Channels',			'value' => UINT,	'multi' => 0, 'traverse' => 1, 'pos' => {0x61 => 1}},
		0x3D7B		=> {'name' => 'ChannelPositions',	'value' => BINARY,	'multi' => 0, 'traverse' => 1, 'pos' => {0x61 => 1}},
		0x2264		=> {'name' => 'BitDepth',			'value' => UINT,	'multi' => 0, 'traverse' => 1, 'pos' => {0x61 => 1}},
		# Content Encoding
		0x2D80		=> {'name' => 'ContentEncodings',	'value' => ELEMENT,	'multi' => 0, 'traverse' => 0, 'pos' => {0x2E => 1}},
		0x2240		=> {'name' => 'ContentEncoding',	'value' => ELEMENT,	'multi' => 1, 'traverse' => 1, 'pos' => {0x2D80 => 1}},
		0x1031		=> {'name' => 'ContentEncodingOrder','value' => UINT,	'multi' => 1, 'traverse' => 1, 'pos' => {0x2240 => 1}},
		0x1032		=> {'name' => 'ContentEncodingScope','value' => UINT,	'multi' => 1, 'traverse' => 1, 'pos' => {0x2240 => 1}},
		0x1033		=> {'name' => 'ContentEncodingType','value' => UINT,	'multi' => 1, 'traverse' => 1, 'pos' => {0x2240 => 1}},
		0x1034		=> {'name' => 'ContentCompression',	'value' => ELEMENT,	'multi' => 1, 'traverse' => 1, 'pos' => {0x2240 => 1}},
		0x0254		=> {'name' => 'ContentCompAlgo',	'value' => UINT,	'multi' => 1, 'traverse' => 1, 'pos' => {0x1034 => 1}},
		0x0255		=> {'name' => 'ContentCompSettings','value' => BINARY,	'multi' => 1, 'traverse' => 1, 'pos' => {0x1034 => 1}},
		0x1035		=> {'name' => 'ContentEncryption',	'value' => ELEMENT,	'multi' => 1, 'traverse' => 1, 'pos' => {0x2240 => 1}},
		0x07E1		=> {'name' => 'ContentEncAlgo',		'value' => UINT,	'multi' => 1, 'traverse' => 1, 'pos' => {0x1035 => 1}},
		0x07E2		=> {'name' => 'ContentEncKeyID',	'value' => BINARY,	'multi' => 1, 'traverse' => 1, 'pos' => {0x1035 => 1}},
		0x07E3		=> {'name' => 'ContentSignature',	'value' => BINARY,	'multi' => 1, 'traverse' => 1, 'pos' => {0x1035 => 1}},
		0x07E4		=> {'name' => 'ContentSigKeyID',	'value' => BINARY,	'multi' => 1, 'traverse' => 1, 'pos' => {0x1035 => 1}},
		0x07E5		=> {'name' => 'ContentSigAlgo',		'value' => UINT,	'multi' => 1, 'traverse' => 1, 'pos' => {0x1035 => 1}},
		0x07E6		=> {'name' => 'ContentSigHashAlgo',	'value' => UINT,	'multi' => 1, 'traverse' => 1, 'pos' => {0x1035 => 1}},
	# Cueing Data
		0x0C53BB6B	=> {'name' => 'Cues',				'value' => ELEMENT,	'multi' => 0, 'traverse' => 0, 'pos' => {0x08538067 => 1}},
		0x3B		=> {'name' => 'CuePoint',			'value' => ELEMENT,	'multi' => 1, 'traverse' => 1, 'pos' => {0x0C53BB6B => 1}},
		0x33		=> {'name' => 'CueTime',			'value' => UINT,	'multi' => 0, 'traverse' => 1, 'pos' => {0x3B => 1}},
		0x37		=> {'name' => 'CueTrackPositions',	'value' => ELEMENT,	'multi' => 1, 'traverse' => 1, 'pos' => {0x3B => 1}},
		0x77		=> {'name' => 'CueTrack',			'value' => UINT,	'multi' => 0, 'traverse' => 1, 'pos' => {0x37 => 1}},
		0x71		=> {'name' => 'CueClusterPosition',	'value' => UINT,	'multi' => 0, 'traverse' => 1, 'pos' => {0x37 => 1}},
		0x1378		=> {'name' => 'CueBlockNumber',		'value' => UINT,	'multi' => 0, 'traverse' => 1, 'pos' => {0x37 => 1}},
		0x6A		=> {'name' => 'CueCodecState',		'value' => UINT,	'multi' => 0, 'traverse' => 1, 'pos' => {0x37 => 1}},
		0x5B		=> {'name' => 'CueReference',		'value' => ELEMENT,	'multi' => 1, 'traverse' => 1, 'pos' => {0x37 => 1}},
		0x16		=> {'name' => 'CueRefTime',			'value' => UINT,	'multi' => 0, 'traverse' => 1, 'pos' => {0x5B => 1}},
		0x17		=> {'name' => 'CueRefCluster',		'value' => UINT,	'multi' => 0, 'traverse' => 1, 'pos' => {0x5B => 1}},
		0x135F		=> {'name' => 'CueRefNumber',		'value' => UINT,	'multi' => 0, 'traverse' => 1, 'pos' => {0x5B => 1}},
		0x6B		=> {'name' => 'CueRefCodecState',	'value' => UINT,	'multi' => 0, 'traverse' => 1, 'pos' => {0x5B => 1}},
	# Attachments
		0x0941A469	=> {'name' => 'Attachments',		'value' => ELEMENT,	'multi' => 0, 'traverse' => 0, 'pos' => {0x08538067 => 1}},
		0x21A7		=> {'name' => 'AttachedFile',		'value' => ELEMENT,	'multi' => 1, 'traverse' => 1, 'pos' => {0x0941A469 => 1}},
		0x067E		=> {'name' => 'FileDescription',	'value' => UTF8,	'multi' => 0, 'traverse' => 1, 'pos' => {0x21A7 => 1}},
		0x066E		=> {'name' => 'FileName',			'value' => UTF8,	'multi' => 0, 'traverse' => 1, 'pos' => {0x21A7 => 1}},
		0x0660		=> {'name' => 'FileMimeType',		'value' => STRING,	'multi' => 0, 'traverse' => 1, 'pos' => {0x21A7 => 1}},
		0x065C		=> {'name' => 'FileData',			'value' => BINARY,	'multi' => 0, 'traverse' => 0, 'pos' => {0x21A7 => 1}},
		0x06AE		=> {'name' => 'FileUID',			'value' => UINT,	'multi' => 0, 'traverse' => 1, 'pos' => {0x21A7 => 1}},
	# Chapters
		0x0043A770	=> {'name' => 'Chapters',			'value' => ELEMENT,	'multi' => 0, 'traverse' => 1, 'pos' => {0x08538067 => 1}},
		0x05B9		=> {'name' => 'EditionEntry',		'value' => ELEMENT,	'multi' => 1, 'traverse' => 1, 'pos' => {0x0043A770 => 1}},
		0x05BC		=> {'name' => 'EditionUID',			'value' => UINT,	'multi' => 0, 'traverse' => 1, 'pos' => {0x05B9 => 1}},
		0x05BD		=> {'name' => 'EditionFlagHidden',	'value' => UINT,	'multi' => 0, 'traverse' => 1, 'pos' => {0x05B9 => 1}},
		0x05DB		=> {'name' => 'EditionFlagDefault',	'value' => UINT,	'multi' => 0, 'traverse' => 1, 'pos' => {0x05B9 => 1}},
		0x05DD		=> {'name' => 'EditionManaged',		'value' => UINT,	'multi' => 0, 'traverse' => 1, 'pos' => {0x05B9 => 1}},
		0x36		=> {'name' => 'ChapterAtom',		'value' => ELEMENT,	'multi' => 1, 'traverse' => 1, 'pos' => {0x05B9 => 1, 0x36 => 1}},
		0x33C4		=> {'name' => 'ChapterUID',			'value' => UINT,	'multi' => 0, 'traverse' => 1, 'pos' => {0x36 => 1}},
		0x11		=> {'name' => 'ChapterTimeStart',	'value' => UINT,	'multi' => 0, 'traverse' => 1, 'pos' => {0x36 => 1}},
		0x12		=> {'name' => 'ChapterTimeEnd',		'value' => UINT,	'multi' => 0, 'traverse' => 1, 'pos' => {0x36 => 1}},
		0x18		=> {'name' => 'ChapterFlagHidden',	'value' => UINT,	'multi' => 0, 'traverse' => 1, 'pos' => {0x36 => 1}},
		0x0598		=> {'name' => 'ChapterFlagEnabled',	'value' => UINT,	'multi' => 0, 'traverse' => 1, 'pos' => {0x36 => 1}},
		0x23C3		=> {'name' => 'ChapterPhysicalEquiv','value' => UINT,	'multi' => 0, 'traverse' => 1, 'pos' => {0x36 => 1}},
		0x0F		=> {'name' => 'ChapterTrack',		'value' => ELEMENT,	'multi' => 0, 'traverse' => 1, 'pos' => {0x36 => 1}},
		0x09		=> {'name' => 'ChapterTrackNumber',	'value' => UINT,	'multi' => 1, 'traverse' => 1, 'pos' => {0x0F => 1}},
		0x00		=> {'name' => 'ChapterDisplay',		'value' => ELEMENT,	'multi' => 1, 'traverse' => 1, 'pos' => {0x36 => 1}},
		0x05		=> {'name' => 'ChapString',			'value' => UTF8,	'multi' => 0, 'traverse' => 1, 'pos' => {0x00 => 1}},
		0x037C		=> {'name' => 'ChapLanguage',		'value' => STRING,	'multi' => 1, 'traverse' => 1, 'pos' => {0x00 => 1}},
		0x037E		=> {'name' => 'ChapCountry',		'value' => STRING,	'multi' => 1, 'traverse' => 1, 'pos' => {0x00 => 1}},
	# Tagging
		0x0254C367	=> {'name' => 'Tags',				'value' => ELEMENT,	'multi' => 1, 'traverse' => 1, 'pos' => {0x08538067 => 1}},
		0x3373		=> {'name' => 'Tag',				'value' => ELEMENT,	'multi' => 1, 'traverse' => 1, 'pos' => {0x0254C367 => 1}},
		0x23C0		=> {'name' => 'Targets',			'value' => ELEMENT,	'multi' => 0, 'traverse' => 1, 'pos' => {0x3373 => 1}},
		0x28CA		=> {'name' => 'TargetTypevalue',	'value' => UINT,	'multi' => 0, 'traverse' => 1, 'pos' => {0x23C0 => 1}},
		0x23CA		=> {'name' => 'TargetType',			'value' => STRING,	'multi' => 0, 'traverse' => 1, 'pos' => {0x23C0 => 1}},
		0x23C9		=> {'name' => 'EditionUID',			'value' => UINT,	'multi' => 1, 'traverse' => 1, 'pos' => {0x23C0 => 1}},
		0x23C4		=> {'name' => 'ChapterUID',			'value' => UINT,	'multi' => 1, 'traverse' => 1, 'pos' => {0x23C0 => 1}},
		0x23C5		=> {'name' => 'TrackUID',			'value' => UINT,	'multi' => 1, 'traverse' => 1, 'pos' => {0x23C0 => 1}},
		0x23C6		=> {'name' => 'AttachmentUID',		'value' => UINT,	'multi' => 1, 'traverse' => 1, 'pos' => {0x23C0 => 1}},
		0x27C8		=> {'name' => 'SimpleTag',			'value' => ELEMENT,	'multi' => 1, 'traverse' => 1, 'pos' => {0x3373 => 1, 0x27C8 => 1}},
		0x05A3		=> {'name' => 'TagName',			'value' => UTF8,	'multi' => 0, 'traverse' => 1, 'pos' => {0x27C8 => 1}},
		0x047A		=> {'name' => 'TagLanguage',		'value' => STRING,	'multi' => 0, 'traverse' => 1, 'pos' => {0x27C8 => 1}},
		0x0484		=> {'name' => 'TagDefault',			'value' => UINT,	'multi' => 0, 'traverse' => 1, 'pos' => {0x27C8 => 1}},
		0x0487		=> {'name' => 'TagString',			'value' => UTF8,	'multi' => 0, 'traverse' => 1, 'pos' => {0x27C8 => 1}},
		0x0485		=> {'name' => 'TagBinary',			'value' => BINARY,	'multi' => 0, 'traverse' => 0, 'pos' => {0x27C8 => 1}},
#			=> {'name' => '',	'value' => ,	'multi' => 1, 'traverse' => 1, 'pos' => {}},
	};
        
}

################################################################################
sub new {
	open(my $temp, $_[1]) or die "ERROR: Can't open file '$_[1]' for reading from matroska::new\n$!\n";
	binmode($temp);
	my $self = {
		'filename' => $_[1],
		'buffersize' => $matroska::DefaultBuffer,
		'buffer' => '',
		'filehandle' => $temp,
		'bufferpos' => 0,
		'useseek' => (($#_ > 1) ? (0 + $_[2]) : (1)),
	};
	bless $self;
	return $self;
}

sub readToBuffer {
	my $self = $_[0];
	my $len = read($self->{'filehandle'}, my $temp, $self->{'buffersize'});
	$self->{'buffer'} .= $temp;
	return $len;
}

sub flush {
	my $self = $_[0];
	if($self->{'bufferpos'} >= $matroska::FlushBuffer) {
		# FLUSH!
		substr($self->{'buffer'}, 0, $self->{'bufferpos'}) = '';
		$self->{'bufferpos'} = 0;
	}
}

################################################################################
sub readBytes {
	my $self = $_[0];
	while($self->{'bufferpos'} + $_[1] > length($self->{'buffer'})) {
		# The buffer is not long enough to return the amount of stuff requested; make it longer!
		unless($self->readToBuffer()) {
			last;
#			die "ERROR: Can't read past end of file";
#			return '';
		}
	}
	# The buffer is now long enough to grab the thigie out of
	my $returnThis = substr($self->{'buffer'}, $self->{'bufferpos'}, $_[1]);
	$self->{'bufferpos'} += $_[1];
	$self->flush();
	return $returnThis;
}

sub readSize {
	my $self = $_[0];
	my $b1 = $self->readBytes(1);
	if(ord($b1) & 0x80) {
		# 1 byte
		return ord($b1) & 0x7f;
	} elsif(ord($b1) & 0x40) {
		# 2 bytes
		$b1 .= $self->readBytes(1);
		return unpack("n", chr(0x40) ^ $b1);
	} elsif(ord($b1) & 0x20) {
		# 3 bytes
		$b1 .= $self->readBytes(2);
		return unpack("N", chr(0) . (chr(0x20) ^ $b1));
	} elsif(ord($b1) & 0x10) {
		# 4 bytes
		$b1 .= $self->readBytes(3);
		return unpack("N", chr(0x10) ^ $b1);
	} elsif(ord($b1) & 0x08) {
		# 5 bytes
		$b1 .= $self->readBytes(4);
		my ($high, $low) = unpack("CN", chr(0x08) ^ $b1);
		$high ? (return Math::BigInt->new("$high")->bmul("4294967296")->badd("$low")->bstr()) : (return $low);
	} elsif(ord($b1) & 0x04) {
		# 6 bytes
		$b1 .= $self->readBytes(5);
		my ($high, $low) = unpack("nN", chr(0x04) ^ $b1);
		$high ? (return Math::BigInt->new("$high")->bmul("4294967296")->badd("$low")->bstr()) : (return $low);
	} elsif(ord($b1) & 0x02) {
		# 7 bytes
		$b1 .= $self->readBytes(6);
		my ($high, $low) = unpack("NN", chr(0) . (chr(0x02) ^ $b1));
		$high ? (return Math::BigInt->new("$high")->bmul("4294967296")->badd("$low")->bstr()) : (return $low);
	} elsif(ord($b1) & 0x01) {
		# 8 bytes
		$b1 .= $self->readBytes(7);
		my ($high, $low) = unpack("NN", chr(0x01) ^ $b1);
		$high ? (return Math::BigInt->new("$high")->bmul("4294967296")->badd("$low")->bstr()) : (return $low);
	} else {
		# SOMETHIN' WEIRD
		return "???";
	}
}

sub readInteger {
	my $self = $_[0];
	my $len = $_[1];
	if($len == 1) {
		# 1 byte
		return ord($self->readBytes(1));
	} elsif($len == 2) {
		# 2 bytes
		return unpack("n", $self->readBytes(2));
	} elsif($len == 3) {
		# 3 bytes
		return unpack("N", chr(0) . ($self->readBytes(3)));
	} elsif($len == 4) {
		# 4 bytes
		return unpack("N", $self->readBytes(4));
	} elsif($len == 5) {
		# 5 bytes
		my ($high, $low) = unpack("CN", $self->readBytes(5));
		$high ? (return Math::BigInt->new("$high")->bmul("4294967296")->badd("$low")->bstr()) : (return $low);
	} elsif($len == 6) {
		# 6 bytes
		my ($high, $low) = unpack("nN", $self->readBytes(6));
		$high ? (return Math::BigInt->new("$high")->bmul("4294967296")->badd("$low")->bstr()) : (return $low);
	} elsif($len == 7) {
		# 7 bytes
		my ($high, $low) = unpack("NN", chr(0) . ($self->readBytes(7)));
		$high ? (return Math::BigInt->new("$high")->bmul("4294967296")->badd("$low")->bstr()) : (return $low);
	} elsif($len == 8) {
		# 8 bytes
		my ($high, $low) = unpack("NN", $self->readBytes(8));
		$high ? (return Math::BigInt->new("$high")->bmul("4294967296")->badd("$low")->bstr()) : (return $low);
	} else {
		# SPECIAL
		die "ERROR: Don't know what length '$len' means at " . $self->tell();
	}
}

sub readFloat {
	my $self = $_[0];
	my $len = $_[1];
	# Need to reverse the bytes for little-endian machines
	if($len == 4) {
		# single
		return unpack('f', scalar reverse($self->readBytes(4)));
		#return unpack('f', $self->readBytes(4));
	} elsif($len == 8) {
		# double
		return unpack('d', scalar reverse($self->readBytes(8)));
		#return unpack('d', $self->readBytes(8));
	} elsif($len == 10) {
		# extended (don't know how to handle it)
		return 'EXTENDED';
	} else {
		# INVALID!!!11
		die "ERROR: Don't know how to make a '$len' byte float at " . $self->tell();
	}
}

sub readID {
	my $self = $_[0];
	my $b1 = $self->readBytes(1);
	my $number;
	if(ord($b1) & 0x80) {
		# 1 byte
		$number = ord($b1) & 0x7f;
	} elsif(ord($b1) & 0x40) {
		# 2 bytes
		$b1 .= $self->readBytes(1);
		$number = unpack("n", chr(0x40) ^ $b1);
	} elsif(ord($b1) & 0x20) {
		# 3 bytes
		$b1 .= $self->readBytes(2);
		$number = unpack("N", chr(0) . (chr(0x20) ^ $b1));
	} elsif(ord($b1) & 0x10) {
		# 4 bytes
		$b1 .= $self->readBytes(3);
		$number = unpack("N", chr(0x10) ^ $b1);
	} else {
		# SPECIAL; just return -1
		return -1;
	}
	return $number;
}

################################################################################
sub seek {
	my ($self, $offset, $whence) = @_;
	my $bufferEnd = tell($self->{'filehandle'});
	my $bufferBegin = $bufferEnd - length($self->{'buffer'});
	my $outsideTell = $bufferBegin + $self->{'bufferpos'};
	my $absOffset;
	if($whence == 0) {
		# Beginning of the file
		$absOffset = $offset;
	} elsif($whence == 1) {
		# Current position
		$absOffset = $outsideTell + $offset;
	}
	if($absOffset >= $bufferBegin && $absOffset < $bufferEnd) {
		# The requested position is within the buffer
		$self->{'bufferpos'} = $absOffset - $bufferBegin;
	} else {
		# Buffer is of no use any more
		$self->{'bufferpos'} = 0;
		$self->{'buffer'} = '';
		seek($self->{'filehandle'}, $absOffset, 0);
	}
}

sub tell {
	# Same as standard tell()
	return(tell($_[0]->{'filehandle'}) - length($_[0]{'buffer'}) + $_[0]{'bufferpos'});
}

################################################################################
sub parse {
	my $self = $_[0];
	my $override = $_[1] ? $_[1] : {};	# For override, -1 is default 0 is no traverse, 1 is traverse, 2 is traverse all
	my $filesize = -s ($self->{'filehandle'});

	return $self->parseRecurse(0,0,'',$override,0);
}

# To be parsed
sub parseRecurse {
	# If all is 0, then elements are parsed normally
	# If all is 1, then all elements are traversed
	my ($self, $from, $to, $parentElement, $override, $all) = @_;
	$self->seek($from, 0);

	my $ret = {};

	while(($to == 0) ? ($self->tell() < -s $self->{'filehandle'}) : ($self->tell() < $to)) {
		my $currentElementBegin = $self->tell();
		my $idNumber = $self->readID();
		if($idNumber == -1) {
			return $ret;
		}

		my $elementSize = $self->readSize();
		my $elementInsideBegin = $self->tell();
		if(defined($matroska::Elements->{$idNumber})) {
			# ID in database; parse
			my $idInfo = $matroska::Elements->{$idNumber};

			if($idInfo->{'pos'}{$parentElement} || ($parentElement && $idInfo->{'pos'}{'all'})) {
				# Element is OK where it is

				my $traverse;

				if($all) {
					$traverse = 2;
				} elsif(defined($override->{$idInfo->{'name'}})) {
					if($override->{$idInfo->{'name'}} == 2) {
					 	$traverse = 2;
					} elsif($override->{$idInfo->{'name'}} == 1) {
						$traverse = 1;
					} elsif($override->{$idInfo->{'name'}} == 0) {
						$traverse = 0;
					} else {
						$traverse = $idInfo->{'traverse'};
					}
				} else {
					$traverse = $idInfo->{'traverse'};
				}

				# Figure out where to put the element
				my $elementPlace;	# This is a reference to the spot to stick the elephant
				if($idInfo->{'multi'}) {
					push(@{$ret->{$idInfo->{'name'}}}, {'size' => $elementSize, 'headersize' => $elementInsideBegin - $currentElementBegin, 'pos' => $currentElementBegin});
					$elementPlace = $ret->{$idInfo->{'name'}}[-1];
				} else {
					$ret->{$idInfo->{'name'}} = {'size' => $elementSize, 'headersize' => $elementInsideBegin - $currentElementBegin, 'pos' => $currentElementBegin};
					$elementPlace = $ret->{$idInfo->{'name'}};
				}

				# Figure out what to do with it
				if($idInfo->{'value'} == ELEMENT) {
					if($traverse == 2) {
						$elementPlace->{'children'} = $self->parseRecurse($self->tell(), $self->tell() + $elementSize, $idNumber, $override, 1);
					} elsif($traverse == 1) {
						$elementPlace->{'children'} = $self->parseRecurse($self->tell(), $self->tell() + $elementSize, $idNumber, $override, 0);
					} else {
						$elementPlace->{'value'} = 'SKIPPED';
						$self->seek($elementSize, 1);
					}
				} elsif($idInfo->{'value'} == UINT || $idInfo->{'value'} == SINT || $idInfo->{'value'} == DATE) {
					$elementPlace->{'value'} = $self->readInteger($elementSize);
				} elsif($idInfo->{'value'} == STRING || $idInfo->{'value'} == UTF8) {
					$elementPlace->{'value'} = $self->readBytes($elementSize);
				} elsif($idInfo->{'value'} == BINARY) {
					$elementPlace->{'value'} = 'BINARY';
					$self->seek($elementSize, 1);
				} elsif($idInfo->{'value'} == FLOAT) {
					$elementPlace->{'value'} = $self->readFloat($elementSize);
				} elsif($idInfo->{'value'} == BLOCK) {
					if($traverse) {
						$elementPlace->{'children'} = $self->readBlock($elementSize);
					} else {
						$elementPlace->{'value'} = 'SKIPPED';
						$self->seek($elementSize, 1);
					}
				} else {
					$elementPlace->{'value'} = 'DEATH';
					$self->seek($elementSize, 1);
				}

			} else {
				# Element does not belong here!
				warn "Warning: Element number $idNumber can not be a child of $parentElement at ", $self->tell(), "!\n";
				$self->seek($elementSize, 1);
			}
		} else {
			# Does not exist in the database, but assume the file is OK (might be a bad idea)
			warn "Warning: Can't find the ID $idNumber at ", $self->tell(), " in the database!\n";
			$self->seek($elementSize, 1);
		}

	}
	return $ret;
}

sub readBlock {
	my ($self, $size) = @_;
	my %out;
	my $blockHeaderLocation = $self->tell();
	my $trackNum = $self->readSize();
	my $timecode = $self->readInteger(2);
	my $bitField = ord($self->readBytes(1));
	my $gap = $bitField & 0x01;
	my $lace = ($bitField & 0x06) >> 1;
	my $reserved = $bitField & 0xf8;
	$out{'track'} = $trackNum;
	$out{'timecode'} = $timecode;
	if($gap) {
		$out{'gap'} = 1;
	}
	if($lace == 0) {
		$out{'frames'}[0] = {'pos' => $self->tell(), 'size' => $size - $self->tell + $blockHeaderLocation};
		$out{'lacing'} = 'None';
	} else {
		my $frames = $self->readInteger(1) + 1;
		my $frameStart = $self->tell();
		if($lace == 1) {
			# Xiph lacing
			$out{'lacing'} = 'Xiph';
			my @sizePerFrame = (0);
			my $totalFrameSize = 0;
			for my $frameNow (2 .. $frames) {
				while(1) {
					my $a = $self->readInteger(1);
					$totalFrameSize += $a;
					if($a == 255) {
						$sizePerFrame[-1] += 255;
					} else {
						$sizePerFrame[-1] += $a;
						push(@sizePerFrame, 0);
						last;
					}
				}
			}
			
			$sizePerFrame[-1] = $size - $self->tell() + $blockHeaderLocation - $totalFrameSize;
			
			$totalFrameSize = 0;
			foreach my $frameSize (@sizePerFrame) {
				push(@{$out{'frames'}}, {'size' => $frameSize, 'pos' => $self->tell() + $totalFrameSize});
				$totalFrameSize += $frameSize;
			}

		} elsif($lace == 2) {
			# Fixed-size lacing
			$out{'lacing'} = 'Fixed';
			my $sizePerFrame = ($size - $self->tell() + $blockHeaderLocation) / $frames;
			$out{'framesize'} = $sizePerFrame;
			for my $frameNow (0 .. $frames - 1) {
				push(@{$out{'frames'}}, {'size' => $sizePerFrame, 'pos' => $frameStart + $frameNow * $sizePerFrame});
			}
		} elsif($lace == 3) {
			# EBML lacing
			$out{'lacing'} = 'EBML';
			my $totalFrameSize = $self->readSize();
			my @sizePerFrame = $totalFrameSize;
			my $prevPos = $self->tell();
			for my $a (3 .. $frames) {
				my $prevPos = $self->tell();
				my $uint = $self->readSize();
				my $thisFrameSize = $sizePerFrame[-1] + $uint - 2 ** (7 * ($self->tell() - $prevPos) - 1) + 1;
				$totalFrameSize += $thisFrameSize;
				push(@sizePerFrame, $thisFrameSize);
			}

			push(@sizePerFrame, $size - $self->tell() + $blockHeaderLocation - $totalFrameSize);

			$totalFrameSize = 0;
			foreach my $frameSize (@sizePerFrame) {
				push(@{$out{'frames'}}, {'size' => $frameSize, 'pos' => $self->tell() + $totalFrameSize});
				$totalFrameSize += $frameSize;
			}

		} else {
			$out{'lacing'} = 'COMPLETELY WRONG! OH NOES!!!11';
		}


	}
	$self->seek($blockHeaderLocation, 0);
	$self->seek($size, 1);
	return \%out;
}

1;
