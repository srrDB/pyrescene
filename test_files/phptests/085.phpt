--TEST--
RarArchive has_property handler is given a closed archive
--SKIPIF--
<?php if(!extension_loaded("rar")) print "skip"; ?>
--FILE--
<?php

$f1 = dirname(__FILE__) . "/latest_winrar.rar";
$a = RarArchive::open($f1);
$a->close();

var_dump(isset($a[0]));

echo "\n";
echo "Done.\n";
--EXPECTF--
Warning: main(): The archive is already closed in %s on line %d
bool(false)

Done.
