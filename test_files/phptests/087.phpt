--TEST--
RarArchive read_property gives a fatal error on a write context
--SKIPIF--
<?php if(!extension_loaded("rar")) print "skip"; ?>
--FILE--
<?php

$f1 = dirname(__FILE__) . "/latest_winrar.rar";
$a = RarArchive::open($f1);

unset($a[0]["jj"]);

//or
//$a[0] *= 6;
//$a[0]["jj"] = "bar";
//$h = &$a[0];

echo "\n";
echo "Done.\n";
--EXPECTF--
Fatal error: main(): A RarArchive object is not modifiable in %s on line %d
