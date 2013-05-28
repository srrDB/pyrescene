#!/bin/bash

cwd="$(pwd)"
find . -regextype posix-extended -iregex '.*\.(srs|srr)' -exec rm {} \;
nfo=$(ls *.nfo 2> /dev/null)
rm -f ${nfo%.nfo}.jpg

if [[ "$1" == "-c" ]]; # if we just want to remove srr and srs files
then
  exit 0;
fi

cd "$(find -L . -regextype posix-extended -iregex '.*\.(mkv|avi)' -exec dirname {} \; | tail -n 1)"
$srs "$(find . -iname  '*.avi' -or -iname '*.mkv' | tail -n 1)"
cd "$cwd"
$srr $(find . -iname '*.sfv' -and -not -name '*[_.-]subs[_.-]*sfv' | paste -s -d' ') -d -p \
-s $(find -L . -iname '*.srs' -or -iname '*.nfo' -or -iname '*.jpg' -or -iname '*.png' -or -name '*[_.-]subs[_.-]*sfv' | paste -s -d' ') || exit 1

if [[ "$1" == "-u" ]];
then
  $srrup *.srr;
  find . -regextype posix-extended -iregex '.*\.(srs|srr)' -exec rm {} \;;
fi