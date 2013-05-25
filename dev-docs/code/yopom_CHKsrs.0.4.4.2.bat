@echo off
REM This is the CHKsrs.bat file. Version 0.4.4.2
REM ------------

IF ~%1==~PASS2 GOTO PASS2

REM --------------------------------------------------------------------------------------------------
REM - Main Routine
REM --------------------------------------------------------------------------------------------------
REM 1st Check to see IF we are SOMEHOW -in- the Sample folder. If so, msg, bail out.
FOR %%t in ("%CD%") do IF $%%~nt==$Sample goto IsSampDir
FOR %%t in ("%CD%") do IF $%%~nt==$Sample goto IsSampDir
FOR %%t in ("%CD%") do IF $%%~nt==$Sample goto IsSampDir
REM Next, If there is ANY avi/mkv ALREADY IN Main dir, bail out, do NOT PROCESS or DELETE
FOR %%T IN (*.avi *.mkv) DO IF EXIST %%T goto NoSamp3
REM Next, check for No sample dir, or no sample in dir
IF NOT EXIST Sample goto NoSampDir
SET @@SampName=
FOR %%T IN (Sample\*.avi Sample\*.mkv) DO IF EXIST %%T SET @@SampName=%%T
if ~%@@SampName%==~ goto NoSamp2

REM Init to Sample NOt Found
SET @@FoundSamp=0
REM Loop through all samples (Handles both avi and mkv types)
FOR %%T IN (Sample\*.avi Sample\*.mkv) DO CALL %0 PASS2 %%T
goto EndMain

:NoSampDir
SET @@status=Error.No.Sample.Folder
goto EndMain2
:IsSampDir
SET @@status=Error.Base.Folder.Is.Sample.Dir_possibly.rars.in.Sample.Folder
goto EndMain2
:NoSamp2
SET @@status=Error.No.Sample.File.In.Sample.Folder
goto EndMain2
:NoSamp3
SET @@status=Error.Sample.File.Exists.In.Main.Folder
goto EndMain2


:EndMain
REM Moved avi / srs cleanup to here, so it will be skipped IF no sample dir, no Sample in dir, or avi/mkv exists in main.
REM This avoids the error where the sample was in the main folder (forgot to be put in the sample folder),
REM   and ends up getting deleted. In addition, new logic implemented here to avoid deletion if (for some odd reason),
REM   we are ALREADY IN the Sample folder (if the only rars found are IN the Sample folder).
if NOT ~%1==~keep FOR %%T in (*.srs *.avi *.mkv) do IF EXIST %%T del %%T
:EndMain2
IF NOT ~"%@@status%"==~"" ECHO !!!! %@@status%
REM Display / Process Sample info here
REM ------------
REM @@SampName has the name of the Sample that was sucessfully rebuilt from rar file @@rar
REM @@status is both an error flag and the actual error message.
REM Output the msgs to console, but leave the 3 vars in env so a calling PROG can process it as well

IF ~"%@@status%"==~"" ECHO  OK! Made srs and REGen OK! (%@@SampName% matched Source rar %@@rar%)
FOR %%T in (@@ext @@FoundSamp @@tmp1 @@tmp2 @@CDnum @@CDnext) DO SET %%T=


goto alldone



REM --------------------------------------------------------------------------------------------------
REM  BEGIN: PASS 2
REM --------------------------------------------------------------------------------------------------
:PASS2
REM If we have already matched a sample, bail out now (Multiple Samples)
IF ~%@@FoundSamp%==~1 goto alldone
REM Use the var @@CDnext to index location of rar files
REM If MultiCD, @@CDnext is "CDx" .. else @@CDnext is "."
SET @@CDnum=1
  REM Assume NOT MultiCD
SET @@CDnext=.
  REM If a CD1 Exists, set to do MultiCD
IF EXIST CD1 SET @@CDnext=CD1

:InLoop
  REM If we have already matched a sample, bail out now
  IF ~%@@FoundSamp%==~1 goto alldone
  SET @@SampName=%2
  REM The location to look will be @@CDnext
  SET @@ext=rar
  IF EXIST %@@CDnext%\*.001 ( SET @@ext=001&goto GotExt )
  IF EXIST %@@CDnext%\*.part1.rar ( SET @@ext=part1.rar&goto GotExt )
  IF EXIST %@@CDnext%\*.part001.rar ( SET @@ext=part001.rar&goto GotExt )
  IF EXIST %@@CDnext%\*.part01.rar SET @@ext=part01.rar
  :GotExt
  FOR %%T in (%@@CDnext%\*.%@@ext%) do SET @@rar=%%T
    REM If no rars found in location being checked, flag as error and bail
  IF ~%@@rar%==~ goto SRSerr1
  REM Always start off with a clear @@status to assume no error
  SET @@status=
  REM If we pass the The -c check, then we have the Sample and rar match
  call srs %@@SampName% -c %@@rar%
  REM Trap compressed rars error NOW!
  if errorlevel 2 if not errorlevel 3 goto SRSerr3
  if errorlevel 1 goto InLoop20
  REM This prob isn't needed, but just in case there's no error, yet no srs, trap it!
     REM (no, don't do this) FOR %%T in (*.srs) do if NOT EXIST %%T goto InLoop20
  SET @@FoundSamp=1
  REM Get the sample name, remove ext, add srs
  FOR %%T IN (%@@SampName%) DO SET @@tmp2=%%~nT.srs
  REM Remake srs.
  call srs %@@tmp2% %@@rar%
  IF ERRORLEVEL 5 if not ERRORLEVEL 6 goto SRSerr2a
  IF ERRORLEVEL 1 goto SRSerr2
  SET @@tmp2=0
  IF EXIST *.avi set @@tmp2=1
  if ~%@@tmp2%==0 ( IF EXIST *.mkv set @@tmp2=1 )
  if ~%@@tmp2%==0 goto SRSerr2
    REM Logic ends here for inner loop

  :InLoop20
    REM Don't repeat loop if Not MultiCD or NEXT CD does not exist
  IF ~%@@CDnext%==~. GOTO LoopEnd

  SET /A @@CDnum +=1 
  SET @@CDnext=CD%@@CDnum%
  IF NOT EXIST %@@CDnext% GOTO LoopEnd

  GOTO InLoop

:SRSerr1
SET @@status=No.rars.Found.In.Location."%@@CDnext%"]
goto alldone
:SRSerr2
SET @@status=On.Attempt.To.REMAKE.sample (%@@SampName% - Source rar %@@rar%)
goto alldone
:SRSerr2a
SET @@status=CRC.Error.Mismatch.Occured.in.REMAKING.sample (%@@SampName% - Source rar %@@rar%)
goto alldone
:SRSerr3
REM A bad sample is also this errorlevel, so redo srs and pipe output to temp, parse tmp for string
REM Assume Compressed rars
SET @@status=Compressed.rars.detected (%@@SampName% - Source rar %@@rar%)
call srs %@@SampName%>%TEMP%\$
Find "Corruption detected: Invalid FourCC" %TEMP%\$>NUL
IF ERRORLEVEL 1 goto SRSerr3a
SET @@status=Corruption.detected-Invalid.FourCC.value (%@@SampName%)
GOTO SRSerr3z
:SRSerr3a
Find "Corruption detected: Invalid chunk length" %TEMP%\$>NUL
IF ERRORLEVEL 1 goto SRSerr3z
SET @@status=Truncated.Sample (%@@SampName%)
:SRSerr3z
IF EXIST %TEMP%\$ del %TEMP%\$>NUL
goto alldone


:LoopEnd
REM End of loop, now if nothing found (%@@FoundSamp=0) tag as error
IF ~%@@FoundSamp%==~1 goto alldone
SET @@status=Error.No.Sample.Matches.Source.Rars
goto alldone

REM --------------------------------------------------------------------------------------------------
REM  END: PASS 2
REM --------------------------------------------------------------------------------------------------


:alldone