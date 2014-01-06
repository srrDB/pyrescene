--TEST--
RarArchive read_property handler basic test
--SKIPIF--
<?php if(!extension_loaded("rar")) print "skip"; ?>
--FILE--
<?php

//see also test #81 for broken archives

$f1 = dirname(__FILE__) . "/latest_winrar.rar";
$f2 = dirname(__FILE__) . "/multi.part1.rar";

echo "* latest_winrar.rar:\n";
$a = RarArchive::open($f1);
for ($i = 0; $i < 2; $i++) {
	echo ($i + 1) . ". $a[$i]\n";
}

echo "\n* multi.part1.rar:\n";
$a = RarArchive::open($f2);
for ($i = 0; $i < 2; $i++) {
	echo ($i + 1) . ". $a[$i]\n";
}

echo "\n";
echo "Done.\n";
--EXPECTF--
* latest_winrar.rar:
1. RarEntry for file "1.txt" (a0de71c0)
2. RarEntry for file "2.txt" (45a918de)

* multi.part1.rar:
1. RarEntry for file "file1.txt" (52b28202)
2. RarEntry for file "file2.txt" (f2c79881)

Done.
