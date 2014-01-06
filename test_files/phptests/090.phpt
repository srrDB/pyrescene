--TEST--
RarArchive has_property gives a fatal error
--SKIPIF--
<?php if(!extension_loaded("rar")) print "skip"; ?>
--FILE--
<?php

$f1 = dirname(__FILE__) . "/latest_winrar.rar";
$a = RarArchive::open($f1);

var_dump(isset($a[0]));
var_dump(!empty($a[0]));

var_dump(isset($a[2]));
var_dump(!empty($a[2]));

var_dump(isset($a["jsdf"]));
var_dump(!empty($a["jlkjlk"]));

echo "\n";
echo "Done.\n";
--EXPECTF--
bool(true)
bool(true)
bool(false)
bool(false)
bool(false)
bool(false)

Done.
