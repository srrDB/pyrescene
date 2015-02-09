--TEST--
rar_list handles files with non-unique entry names
--SKIPIF--
<?php if(!extension_loaded("rar")) print "skip"; ?>
--FILE--
<?php

$file = RarArchive::open(dirname(__FILE__) . '/repeated_name.rar');

$entries = rar_list($file);
foreach ($entries as $e) {
	echo $e->getPosition() . ". $e\n";
}
echo "\n";

echo "Done.\n";
--EXPECTF--
0. RarEntry for file "file.txt" (ae2a88a7)
1. RarEntry for file "file.txt" (771df243)

Done.
