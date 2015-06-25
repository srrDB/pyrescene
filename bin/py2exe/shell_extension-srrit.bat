@ECHO OFF
title pyReScene Auto
CD %1

REM %1: path to clicked release folder
REM %1\..: path where the release folder is in
REM -c: works for compressed archives (it's best to always keep this)
REM -s: the sample is verified against the main video files (much slower)
REM -v: an SRR file for vobsubs is included (install unrar or WinRAR)
REM -o: sets the output path (where the .srr files will appear)
REM -r: can create .srr files recursively
REM     (it'll find all releases in a folder)

REM -y: always yes for all prompts
REM -n: always no for all prompts
REM     (when it asks to replace an existing .srr file)
python.exe %~dp0pyrescene.exe %1 -c -s -v -o %1\.. -r

REM Keeps the results on screen when the process has errors
IF %ERRORLEVEL% GTR 0 PAUSE

REM Uncomment the next line by removing REM to always keep the results on screen
REM PAUSE

REM Ctrl + C will cancel the SRR creation process (or Ctrl + Break)