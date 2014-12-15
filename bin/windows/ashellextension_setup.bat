@ECHO OFF
title Shell Extension for pyReScene Auto
echo.
echo This script will add a right click context menu item on folders,
echo to create an SRR file for the selected folder.
echo Edit ashellextension_srrit.bat to change the behavior.
echo.
echo What do you want to do?
echo [I]nstall
echo [U]ninstall
echo [E]xit

:input
set INPUT=
set /P INPUT=Select the answer: %=%
if "%INPUT%"=="" goto input
if /I %INPUT% == I goto install
if /I %INPUT% == U goto uninstall
if /I %INPUT% == E goto finish
goto input

:install
cls
echo Installing
echo.
echo Adding all bat files to path...
rem CALL add_to_path.bat > NUL
echo.
echo Adding Shell Extension...
reg add "HKCU\Software\Classes\Directory\shell\pyReSceneAuto" /ve /t REG_SZ /d "pyReScene Auto" /f
reg add "HKCU\Software\Classes\Directory\shell\pyReSceneAuto\command" /ve /t REG_SZ /d "\"%~dp0ashellextension_srrit.bat\" \"%%1\"" /f
goto finish

:uninstall
cls
echo Uninstalling
echo.
echo Removing Shell Extension
reg delete "HKCU\Software\Classes\Directory\shell\pyReSceneAuto" /f
goto finish

:finish
echo.
echo Done!
echo.
pause