--TEST--
RarArchive traversal with multi-part archive
--SKIPIF--
<?php if(!extension_loaded("rar")) print "skip"; ?>
--FILE--
<?php
$rarF = RarArchive::open(dirname(__FILE__) . '/multi.part1.rar');
foreach ($rarF as $k => $rarE) {
	echo "$k. $rarE\n";
}
echo "Done\n";
--EXPECTF--
0. RarEntry for file "file1.txt" (52b28202)
1. RarEntry for file "file2.txt" (f2c79881)
2. RarEntry for file "file3.txt" (bcbce32e)
Done
