@ECHO OFF
title pyReScene Auto
CD %1

REM %1: path to clicked release folder
REM %1\..: path where the release folder is in
REM -c: works for compressed archives
REM -s: the sample is verified against the main video files
REM -v: an SRR file for vobsubs is included (install unrar or WinRAR)
REM -o: sets the output path
REM -r: can create .srr files recursively
REM -y or -n: always yes or no for all prompts
python.exe "%~dp0..\pyrescene.py" %1 -c -s -v -o %1\.. -r

REM Uncomment by removing REM to always keep the results on screen
REM PAUSE

REM Keeps the results on screen when the process has errors
IF %ERRORLEVEL% GTR 0 PAUSE

REM Ctrl + C will cancel the SRR creation process (or Ctrl + Break)