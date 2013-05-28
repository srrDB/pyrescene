--TEST--
Traversal of RarArchive with foreach by reference gives error
--SKIPIF--
<?php if(!extension_loaded("rar")) print "skip"; ?>
--FILE--
<?php

$f1 = dirname(__FILE__) . "/latest_winrar.rar";
$a = RarArchive::open($f1);

foreach ($a as &$v) {
	die("shouldn't have gotten here");
}

echo "\n";
echo "Done.\n";
--EXPECTF--
Fatal error: main(): An iterator cannot be used with foreach by reference in %s on line %d
