--TEST--
File stream EOF behavior
--SKIPIF--
<?php if(!extension_loaded("rar")) print "skip"; ?>
--FILE--
<?php

$a = RarArchive::open(dirname(__FILE__) . "/multi.part1.rar");
$a2 = RarArchive::open(dirname(__FILE__) . "/4mb.rar");

function echoeof($stream) {
	echo feof($stream)?"At eof":"Not at eof";
	echo "\n";
}

echo "* First fread is given file size:\n";
$stream = $a->getEntry("file1.txt")->getStream();
echoeof($stream);
var_dump(fread($stream, 18));
echoeof($stream);
var_dump(fread($stream, 1));
echoeof($stream);

echo "\n* First fread is given size - 1:\n";
$stream = $a->getEntry("file1.txt")->getStream();
echoeof($stream);
var_dump(fread($stream, 17));
echoeof($stream);
var_dump(fread($stream, 1));
echoeof($stream);
var_dump(fread($stream, 1));
echoeof($stream);

echo "\n* First fread is given size + 1:\n";
$stream = $a->getEntry("file1.txt")->getStream();
echoeof($stream);
var_dump(fread($stream, 19));
echoeof($stream);

echo "\n* Read is aligned with dictionary, buffer and file size:\n";
$stream = $a2->getEntry("4mb.txt")->getStream();
echoeof($stream);
var_dump(strlen(fread($stream, 4194304)));
echoeof($stream);
var_dump(strlen(fread($stream, 1)));
echoeof($stream);

echo "\n* Read is dictionary, buffer and file size - 1:\n";
$stream = $a2->getEntry("4mb.txt")->getStream();
echoeof($stream);
var_dump(strlen(fread($stream, 4194303)));
echoeof($stream);
var_dump(strlen(fread($stream, 1)));
echoeof($stream);
var_dump(strlen(fread($stream, 1)));
echoeof($stream);

echo "\n* Read is dictionary, buffer and file size + 1:\n";
$stream = $a2->getEntry("4mb.txt")->getStream();
echoeof($stream);
var_dump(strlen(fread($stream, 4194305)));
echoeof($stream);

echo "\n";
echo "Done.\n";
--EXPECTF--
* First fread is given file size:
Not at eof
string(18) "contents of file 1"
Not at eof
string(0) ""
At eof

* First fread is given size - 1:
Not at eof
string(17) "contents of file "
Not at eof
string(1) "1"
Not at eof
string(0) ""
At eof

* First fread is given size + 1:
Not at eof
string(18) "contents of file 1"
At eof

* Read is aligned with dictionary, buffer and file size:
Not at eof
int(4194304)
Not at eof
int(0)
At eof

* Read is dictionary, buffer and file size - 1:
Not at eof
int(4194303)
Not at eof
int(1)
Not at eof
int(0)
At eof

* Read is dictionary, buffer and file size + 1:
Not at eof
int(4194304)
At eof

Done.
