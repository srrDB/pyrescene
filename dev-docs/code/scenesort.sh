#!/bin/bash


##rescene options
SRREXE="$HOME/.scenesort/srr.exe" ##set location, leave 'srr.exe' suffix. will download (prompt) when not found,
SRSEXE="$HOME/.scenesort/srs.exe" ##as above.
LOCALSRR="../.rescene" ##path containing local SRRs.
STORESRR="1" ##remove all SRR/SRS if 0. (when using online database.)

## AweScript - written by Guber (goober) - is utilised by this script.
## http://x264.rescene.com/awescript/
AWESCRIPT="$HOME/.scenesort/awescript.py" ##location - will download if not found.

##default dir. locations
MOVE_FAILED="0" ##set to 1 to move directories to locations specified below.
NUKEDIR="$HOME/downloads/failed/nuked" ##directory for nuked releases. (orlydb query)
P2PDIR="$HOME/downloads/failed/notinpredb" ##directory for non-scene releases. (orlydb query)
BADCRC="$HOME/downloads/failed/badcrc" ##directory for releases that fail SFV check.

## end of user config.


TITLE="SceneSort"
VERSION="4.20102911"

IFS=$'\n'

SRREXEFS="33792"
SRSEXEFS="72192"
srrlatest=$(echo "${SRREXE%/*}/srr.1.2.rar")
srslatest=$(echo "${SRSEXE%/*}/srs.1.2.rar")

case $(uname -s) in
	Linux)
	stat_ () { stat -c %s "$1"; }
	;;
	Darwin|*BSD)
	stat_ () { stat "$1" | cut -d' ' -f8; }
	;;
esac


##


awescript_download () {
echo -e "\n?? Download and setup AweScript? (y, n): "; read

[ "$REPLY" != "y" ] && die

curl --create-dirs "http://x264.rescene.com/awescript/awescript_src.rar" -o "${AWESCRIPT%/*}/awescript_src.rar" && \
unrar e -o+ "${AWESCRIPT%/*}/awescript_src.rar" "awescript.py" "${AWESCRIPT%/*}"

##No sed -i for compat. issues.
[ -f "${AWESCRIPT%/*}/awescript.py" ] && cat "${AWESCRIPT%/*}/awescript.py" | sed -e 's|/usr/local/bin/srs.exe|'$SRSEXE'|g' \
-e 's|/usr/local/bin/srr.exe|'$SRREXE'|g' > "${AWESCRIPT%/*}/_awescript.py" && \
mv -f "${AWESCRIPT%/*}/_awescript.py" "${AWESCRIPT%/*}/awescript.py" && rm -f "${AWESCRIPT%/*}/awescript_src.rar" &> "/dev/null"

[ ! -f "$AWESCRIPT" ] && echo -e "\n@@ Error downloading AweScript." && die
echo -e "\n>> Sucessfully downloaded AweScript."
}


##


awescript () {
[ ! -d "$LOCALSRR" ] && mkdir -p "$LOCALSRR"
IFS=$' '; python $(echo "$AWESCRIPT $AWP") "$PWD"

[ "$?" != "0" ] && echo -e "\n@@ AweScript error." && die
IFS=$'\n'
}


##


type_allpkgreq () {
for pkg in ${pkgreq[*]}; do
	! $(type "$pkg" &> "/dev/null") && echo -e "\n@@ $pkg is required." && ((pkgreqcounter++))
done

[ -n "$pkgreqcounter" ] && die
}


##


rescene_verchk () {
[ ! -f "$SRREXE" -o ! -f "$SRSEXE" ] && rescene_download
[[ $(stat_ "$SRREXE") != "$SRREXEFS" ]] && echo -e "\n@@ ReScene(srr.exe) is out of date." && rescene_download
[[ $(stat_ "$SRSEXE") != "$SRSEXEFS" ]] && echo -e "\n@@ ReSample(srs.exe) is out of date." && rescene_downoad
return 0
}


##


rescene_download () {
echo -e "\n?? Download and setup ReScene/ReSample? (y, n): "; read

[ "$REPLY" != "y" ] && die

for rescene_latest in "$srrlatest" "$srslatest"; do
	
	[ "$rescene_latest" = "$srslatest" ] && _parent="resample/"
	curl --create-dirs "http://rescene.com/$_parent${rescene_latest##*/}" -o "$rescene_latest"
	
	[ "$?" = "0" ] && unrar e -o+ "$rescene_latest" $(unrar lb "$rescene_latest" | egrep -i "srr\.exe|srs\.exe") "${rescene_latest%/*}" && \
	rm -f "$rescene_latest" &> "/dev/null"
done

rescene_verchk
[ "$?" != "0" ] && echo -e "\n@@ Error downloading ReScene/ReSample." && die
echo -e "\n>> Sucessfully downloaded ReScene/ReSample."
}


##


rescene_online_srrdb () {
$(echo "${PWD##*/}" | egrep -qi "x264|h264") && rscat="x264"
$(echo "${PWD##*/}" | egrep -qi "xvid|divx") && rscat="xvid"

[ -z "$rscat" ] && echo -e "\n@@ Release format not recognised." && return 1

$(echo "${PWD##*/}" | egrep -qi "s[0-9][0-9]|e[0-9][0-9]|ep\.[0-9]|episode|pt\.|part") && rssec="TV"
[ "$rssec" != "TV" ] && rssec="Movies"

curl "http://$rscat.rescene.com/download.ashx?Section=$rssec&Release=${PWD##*/}" -o "${PWD##*/}.srr"
if [ -f "${PWD##*/}.srr" -a $(stat_ "${PWD##*/}.srr") -ge "1000" ]; then
	echo -e "\n>> SRR found in online ReScene database."
else
	rm -f "${PWD##*/}.srr" &> "/dev/null"
	echo -e "\n@@ SRR not found in online ReScene database." && return 1
fi
	
if [ "$STORESRR" = "1" ]; then
	[ ! -d "$LOCALSRR" ] && mkdir -p "$LOCALSRR"
	[ ! -f "$LOCALSRR/${srr##*/}" ] && cp -f "${PWD##*/}.srr" "$LOCALSRR"
fi
}


##


rescene_local_srrdb () {
[ -f "$LOCALSRR/${PWD##*/}.srr" ] && cp -f "$LOCALSRR/${PWD##*/}.srr" "$PWD" && echo -e "\n>> SRR found in local ReScene database." && return 0
	
echo -e "\n@@ SRR not found in local ReScene database." && return 1
}


##


rescene_prepare () {
find . -mindepth 1 -type f -exec mv -f {} "$PWD" \; &> "/dev/null" 
find . -type d -empty -exec rm -rf {} \; &> "/dev/null"
}


##


rescene_srr_rebuild () {
[ ! -f "${PWD##*/}.srr" ] && echo -e "\n@@ No SRR found." && die

toprar=$(mono "$SRREXE" "${PWD##*/}.srr" -l | grep "RAR Files:" -A1 | tail -n 1 | sed -r 's/^[ \t]*//;s/[ \t]*$//;s/(.*)\///g')
[ -f "$toprar" ] && echo -e "\n>> RARs exist - Not attempting to reconstruct." && mono "$SRREXE" "${PWD##*/}.srr" -x -y && return 0

mono "$SRREXE" "${PWD##*/}.srr" -r -y

if [ "$?" = "0" -a -f "$toprar" ]; then
	srrfext=($(mono "$SRREXE" "${PWD##*/}.srr" -l | grep "Archived Files:" -A20 | egrep -i "\.[a-z]|\.[0-9]" | sed -e 's/^[ \t]*//;s/[ \t]*$//'))
	rm -f $(ls -A | grep "*.${srrfext[*]##*.}") &> "/dev/null"
	echo -e "\n>> RARs successfully reconstructed."
else
	[ -f "$toprar" ] && rm -f "$toprar" &> "/dev/null"
	echo -e "\n@@ Error reconstructing RARs." && die
fi
}


##


resample_srs_rebuild () {
for srs in $(ls -A | grep -i "\.srs$"); do

	sample=$(mono "$SRSEXE" "$srs" -l | grep -i "Sample Name:" | cut -d' ' -f3)
	[ -f "$sample" ] && echo -e "\n>> Sample exists - Not attempting to reconstruct." && continue

	for input in $(ls -A | egrep -i "(\.avi|\.mkv|\.rar|\.001)$" | sort); do
		[ ! -f "$input" ] && echo -e "\n@@ No suitable input files found." && return 1
		
		mono "$SRSEXE" "$srs" "$input" -y

		[ "$?" = "0" ] && echo -e "\n>> Sample successfully reconstructed." && rm -f "$srs" &> "/dev/null" && break
		rm -f "$sample" &> "/dev/null"
		echo -e "\n@@ Error reconstructing sample." && return 1
	done
done
}



##


cfv_verify () {
[ $(ls -AR | grep -ic "\.sfv$") = "0" ] && echo -e "\n@@ No SFV found." && die

cfv -vsnr -t sfv
[ "$?" = "0" ] && echo -e "\n>> SFV passed verification." && return 0

echo -e "\n@@ SFV failed verificiation~!"
[ "$MOVE_FAILED" = "1" ] && { [ ! -d "$BADCRC" ] && mkdir -p "$BADCRC"; mv -f "$PWD" "$BADCRC" &> "/dev/null" && die; }
}


##


orlydb_scrape () {
curl -s "http://www.orlydb.com/?q=\"${PWD##*/}\"" -o "${PWD##*/}.orly"
[ "$?" != "0" ] && echo -e "\n@@ Error connecting to ORLYDB." && return 2

orlyinfo=$(grep -a "class=\"release\">${PWD##*/}<" "${PWD##*/}.orly" -A3 -B3)
rm -f "${PWD##*/}.orly" &> "/dev/null"
if [ -z "$orlyinfo" ]; then 
	echo -e "\n@@ ${PWD##*/} not found in ORLYDB."
	[ "$MOVE_FAILED" = "1" ] && { [ ! -d "$P2PDIR" ] && mkdir -p "$P2PDIR"; mv -f "$PWD" "$P2PDIR" &> "/dev/null" && die; }
	return 2
fi

orlycat=$(echo "$orlyinfo" | grep "class=\"section\">" | cut -d'>' -f3 | cut -d'<' -f1)
orlytime=$(echo "$orlyinfo" | grep "class=\"timestamp\">" | cut -d'>' -f2 | cut -d'<' -f1)
echo -e "\n>> ORLYDB :: [$orlytime] :: [$orlycat]"

orlynuke=$(echo "$orlyinfo" | grep "class=\"nuke\">" | cut -d'>' -f3 | cut -d'<' -f1)
if [ -n "$orlynuke" ]; then
	echo -e "\n@@ NUKE: $orlynuke"
	[ "$MOVE_FAILED" = "1" ] && { [ ! -d "$NUKEDIR" ] && mkdir -p "$NUKEDIR"; mv -f "$PWD" "$NUKEDIR" &> "/dev/null" && die; }
fi
}
		

##


die () {
echo -e "\n@@ Error while processing." && exit 1
}


##


usage () {
echo -e "\n>> $TITLE - $VERSION"
echo -e '\nusage: scenesort [-options] [--switch path] inputdir'
echo -e '\noptions:'
echo -e '\t-R\t- run script recursively.'
echo -e '\n\t-A\t- AweScript - process directory - create SRR/unrar/etc.'
echo -e '\n\t-o\t- download SRR from online ReScene database.'
echo -e '\n\t-l\t- use SRR from local ReScene database.'
echo -e '\n\t-r\t- ReScene - reconstruct original RARs.'
echo -e '\n\t-s\t- ReSample - reconstruct original sample.'
echo -e '\n\t-c\t- AweScript - create original directory structure. (CDn/Subs/Sample/Extras.)'
echo -e '\n\t-v\t- CFV - verify all SFV.'
echo -e '\n\t-n\t- ORLYDB - scrape online database for predate and nuke status.'
echo -e '\n\nswitches: \n\t--srrexe \n\t--srsexe \n\t--localsrr \n\t--storesrr \n\t--awescript \n\t--move-failed \n\t--nukedir \n\t--p2pdir \n\t--badcrc'
echo -e '\n\nthanks to testers: Sleepstre + AWingsFan [Debian], odm [Gentoo] and lhbandit [OSX]'
}


##


while [ "$#" -ne "0" ]; do
	case $1 in
		--help)
		usage
		exit 0
		;;
		--srrexe)
		shift; SRREXE="$1"
		[ ! -f "$SRREXE" ] && echo -e "\n@@ $SRREXE not found." && die
		;;
		--srsexe)
		shift; SRSEXE="$1"
		[ ! -f "$SRSEXE" ] && echo -e "\n@@ $SRSEXE not found." && die
		;;
		--localsrr)
		shift; LOCALSRR="$1"
		;;
		--storesrr)
		shift; [ "$1" -ge "2" ] && echo -e "\n@@ STORESRR must be 1 or 0." && die
		STORESRR="$1"
		;;
		--awescript)
		shift; AWESCRIPT="$1"
		[ ! -f "$AWESCRIPT" ] && echo -e "\n@@ $AWESCRIPT not found." && die
		;;
		--move-failed)
		shift; [ "$1" -ge "2" ] && echo -e "\n@@ MOVE_FAILED must be 1 or 0." && die
		MOVE_FAILED="$1"
		;;
		--nukedir)
		shift; NUKEDIR="$1"
		;;
		--p2pdir)
		shift; P2PDIR="$1"
		;;
		--badcrc)
		shift; BADCRC="$1"
		;;
		-*)
		while getopts ":hRAolrscvn" opt $1; do
		case "$opt" in
			h)
			usage
			exit 0
			;;
			R)
			RECURSIVE="1"
			_swopt=$(echo "$@" | sed -e 's/'$opt'//' | cut -d'/' -f1)
			;;
			A)
			opt_A="1"
			pkgreq+=("python" "mono")
			;;
			o)
			opt_o="1"
			pkgreq+=("curl")
			;;
			l)
			opt_l="1"
			;;
			r)
			opt_r="1"
			pkgreq+=("mono")			
			;;
			s)
			opt_s="1"
			pkgreq+=("mono")
			;;
			c)
			opt_c="1"
			pkgreq+=("python" "mono")
			;;
			v)
			opt_v="1"
			pkgreq+=("cfv")
			;;
			n)
			opt_n="1"
			pkgreq+=("curl")
			;;
		esac
		done
		;;
		*)
		INPUTDIR="$1"
		[ ! -d "$INPUTDIR" ] && echo -e "\n@@ Input directory: $INPUTDIR not found." && die
		;;
	esac
	shift
done

[ -z "$INPUTDIR" ] && echo -e "\n@@ No input directory specified." && die

[ "$RECURSIVE" = "1" ] && {
	IFS=$' ';
	find "$INPUTDIR" -mindepth 1 -maxdepth 1 -type d ! -empty | sort | while read subdir; do
	bash $(echo "$0" "$_swopt") "$subdir"; done
	exit
}

cd "$INPUTDIR"

echo -e "\n>> Processing: ${PWD##*/}~"

pkgreq+=("unrar") && type_allpkgreq

[ ! -f "$SRREXE" -o ! -f "$SRSEXE" ] && [ -n "$opt_A" -o -n "$opt_r" -o -n "$opt_s" -o -n "$opt_c" ] && rescene_download

[ ! -f "$AWESCRIPT" ] && [ -n "$opt_A" -o -n "$opt_c" ] && awescript_download

[ "$opt_n" = "1" ] && orlydb_scrape

[ "$opt_A" = "1" -a "$opt_v" = "1" ] && cfv_verify

[ "$opt_A" = "1" ] && AWP="--srr-dir=$LOCALSRR -demrsp" && awescript

[ "$opt_l" = "1" ] && rescene_local_srrdb

[ "$opt_o" = "1" -a ! -f "${PWD##*/}.srr" ] && rescene_online_srrdb

[ "$opt_r" = "1" -o "$opt_s" = "1" ] && rescene_verchk && rescene_prepare

[ "$opt_r" = "1" ] && rescene_srr_rebuild

[ "$opt_s" = "1" ] && { [ -z "$opt_r" -a -f "${PWD##*/}.srr" ] && mono "$SRREXE" "${PWD##*/}.srr" -x -y; resample_srs_rebuild; }

rm -f $(ls -A | grep -i "\.srs$") &> "/dev/null"

[ "$LOCALSRR" != "$PWD" ] && rm -f "${PWD##*/}.srr" &> "/dev/null"

[ "$opt_c" = "1" ] && AWP="--no-srr --no-srs --move-extracted-cds" && awescript

[ "$opt_v" = "1" -a -z "$opt_A" ] && cfv_verify

echo -e "\n>> Directory processed." && exit