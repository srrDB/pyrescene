@ECHO OFF
REM Try to recreate RARs based on RAR volume or .sfv file and trial/error.
REM Requires Python 3
python.exe %~dp0..\..\rerar\rerar.py %*