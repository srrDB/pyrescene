Read README for general information about the project. (open with Notepad)

- Extract all files to a folder. Add that folder to your path.
  Run add_current_dir_to_path.bat with administrator rights or
  do it manually: http://www.computerhope.com/issues/ch000549.htm
- Install UnRAR (free) or WinRAR to create .srr files for vobsubs
  http://www.rarlab.com/rar_add.htm
- Run the commands auto, srr, srs,... from anywhere on the command line.

Applications rundown
====================

auto:       create .srr files with best settings
pyrescene:  same, but without any defaults
srr:        reconstruct RAR archives; manual .srr creation
srs:        reconstruct samples or fix a single track; create .srs manually
retag:      fix all tracks of a music release
preprardir: preprocessing step for compressed RAR reconstruction

Best settings script
====================

This script calls pyReScene Auto with the best possible settings.
You can do
	auto [parameters here]
instead of each time:
	pyrescene --best [parameters here]
Note: no need to append .exe or .bat.

You can create your own alternatives for other tools in a similar way.
e.g. srr.bat that has -z and -t filled in with your defaults

Context menu
============

Run the setup.bat file of the shell extension as administrator.
A command window will show. Follow the menu to install or remove.
Do not move the srrit.bat file to another directory afterwards or you'll have
to rerun the setup for it to start working again.
