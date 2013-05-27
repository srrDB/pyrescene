--TEST--
RarEntry::getStream handles files with non-unique entry names
--SKIPIF--
<?php if(!extension_loaded("rar")) print "skip"; ?>
--FILE--
<?php

$file = RarArchive::open(dirname(__FILE__) . '/repeated_name.rar');

foreach ($file as $e) {
	$stream = $e->getStream();
	if ($stream) {
		echo $e->getPosition() . ". $e\n";
		echo stream_get_contents($stream);
		echo "\n";
	}
}

echo "Done.\n";
--EXPECTF--
0. RarEntry for file "file.txt" (ae2a88a7)
Content of first file.
1. RarEntry for file "file.txt" (771df243)
Content of second file.
Done.
