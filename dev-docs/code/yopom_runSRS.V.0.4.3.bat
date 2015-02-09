@ECHO OFF
REM This is the runSRS.bat file. Version 0.4.3
if %1~==INNER~ goto INNER

REM --------------------------------------------------------------------------------
REM Set this location to the location of where the CHKsrs bat file is located.
REM Keep the trailing path sep in the name ('\')
REM  i.e.  "c:\" ... or ... "d:\tools\" ... or ... c:\windows\system32\"
SET zzzrunSRSloc=k:\
REM --------------------------------------------------------------------------------

REM -------------------------------------------------------------
REM - Get full path and name of the base batch file name we are running (%0)
FOR %%T in (%0) DO SET @Batchname=%%~fT
REM Create the Main and error log file names
REM   Create a dynamic date-time string to be appended to the log file names
set @@dt=%DATE%:%TIME%
FOR /F "tokens=2-7 delims=/:., " %%A in ("%@@dt%") do SET @@result=.%%A.%%B.%%C-%%D.%%E.%%F
SET @ErrLogFile=%zzzrunSRSloc%runSRS.ERRLOG%@@result%.txt
SET @LogFile=%zzzrunSRSloc%runSRS.LOG%@@result%.txt
ECHO Main Logfile: %@LogFile%
ECHO  ERR Logfile: %@ErrLogFile%

REM This is the main loop entry point
FOR /D %%T in (*.*) do call %@Batchname% INNER "%%T"
FOR %%T in (@Batchname @LogFile @@sErrLogFile @@trap) DO SET %%T=
goto alldone


:INNER
cd %2
REM Look for a trigger condition
FOR %%T IN (*.rar *.001 CD1\*.rar CD1\*.001 CD2\*.rar CD2\*.001 CD3\*.rar CD3\*.001 CD4\*.rar CD4\*.001) do IF EXIST %%T goto TestSamp
REM Recurse deeper yet!
FOR /D %%T in (*.*) do call %@Batchname% INNER "%%T"
goto DOcdBK
:TestSamp
REM -------------------------------------------------------------
REM Found a folder with rars, walk no further and process this folder!
call %zzzrunSRSloc%chkSRS
IF NOT ~"%@@status%"==~"" goto WasErr
ECHO ******** PASSED: [%2]-[%@@SampName% matched Source rar %@@rar%]>>%@LogFile%
goto DOcdBK
:WasErr
rem ECHO !!!ERROR!!! %@@status% [%2]
ECHO !!!ERROR!!! %@@status% [%CD%]>>%@ErrLogFile%
:DOcdBK
cd ..



:alldone