--TEST--
Stream wrapper relative path test
--SKIPIF--
<?php
if(!extension_loaded("rar")) die("skip");
--CLEAN--
<?php
unlink(dirname(__FILE__) . '/temp/tmp.rar');
rmdir(dirname(__FILE__) . "/temp");
--FILE--
<?php
mkdir(dirname(__FILE__) . "/temp");
chdir(dirname(__FILE__) . "/temp");

echo "Test relative to working dir:\n";
$stream = fopen("rar://" .
	'../latest_winrar.rar' .
	"#1.txt", "r");
var_dump(stream_get_contents($stream));

echo "\nTest with include path:\n";
copy(dirname(__FILE__) . '/latest_winrar.rar',
	 dirname(__FILE__) . '/temp/tmp.rar');
chdir(dirname(__FILE__));

//now with include
echo "Should fail (not in include):\n";
$stream = fopen("rar://" .
	'tmp.rar' .
	"#1.txt", "r");
	
echo "\nShould fail (include unused):\n";
	
set_include_path(dirname(__FILE__). '/temp');
$stream = fopen("rar://" .
	'tmp.rar' .
	"#1.txt", "r");
	
echo "\nShould succeed:\n";
$stream = fopen("rar://" .
	'tmp.rar' .
	"#1.txt", "r", true);
var_dump(stream_get_contents($stream));

echo "Done.\n";
--EXPECTF--
Test relative to working dir:
string(5) "11111"

Test with include path:
Should fail (not in include):

Warning: fopen(rar://tmp.rar#1.txt): failed to open stream: Error opening RAR archive %stmp.rar: ERAR_EOPEN (file open error) in %s on line %d

Should fail (include unused):

Warning: fopen(rar://tmp.rar#1.txt): failed to open stream: Error opening RAR archive %stmp.rar: ERAR_EOPEN (file open error) in %s on line %d

Should succeed:
string(5) "11111"
Done.

