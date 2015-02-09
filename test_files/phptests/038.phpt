--TEST--
RarArchive get iterator on closed file
--SKIPIF--
<?php if(!extension_loaded("rar")) print "skip"; ?>
--FILE--
<?php
$rarF = RarArchive::open(dirname(__FILE__) . '/latest_winrar.rar');
$rarF->close();
foreach ($rarF as $k => $rarE) {
	echo "$k. $rarE\n";
	unset($rarE);
}
echo "Done.\n";
--EXPECTF--
Fatal error: main(): The archive is already closed, cannot give an iterator in %s on line %d
