@ECHO OFF
REM "Ability to do srr *.srr -x  and have it show up in their folders"
FOR %%S IN (*.srr) DO (
	python.exe %~dp0..\srr.py %%S -x -p -o %%~nS
)