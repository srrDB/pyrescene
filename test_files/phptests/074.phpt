--TEST--
RarEntry::extract handles files with non-unique entry names
--SKIPIF--
<?php if(!extension_loaded("rar")) print "skip"; ?>
--CLEAN--
<?php
$dest = dirname(__FILE__) . "temp_file";
@unlink($dest);
--FILE--
<?php

$file = RarArchive::open(dirname(__FILE__) . '/repeated_name.rar');
$dest = dirname(__FILE__) . "temp_file";

foreach ($file as $e) {
	$res = $e->extract("", $dest);
	if ($res) {
		echo $e->getPosition() . ". $e\n";
		echo file_get_contents($dest);
		echo "\n";
	}
	else {
		die("failed extraction");
	}
}

echo "Done.\n";
--EXPECTF--
0. RarEntry for file "file.txt" (ae2a88a7)
Content of first file.
1. RarEntry for file "file.txt" (771df243)
Content of second file.
Done.
