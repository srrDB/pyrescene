--TEST--
RarEntry::getPosition() test
--SKIPIF--
<?php if(!extension_loaded("rar")) print "skip"; ?>
--FILE--
<?php

$file = RarArchive::open(dirname(__FILE__) . '/multi.part1.rar');

foreach ($file as $e) {
	echo $e->getPosition() . ". $e\n";
}
echo "\n";

echo "Done.\n";
--EXPECTF--
0. RarEntry for file "file1.txt" (52b28202)
1. RarEntry for file "file2.txt" (f2c79881)
2. RarEntry for file "file3.txt" (bcbce32e)

Done.
