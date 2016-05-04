--TEST--
rar_solid_is() basic test
--SKIPIF--
<?php if(!extension_loaded("rar")) print "skip"; ?>
--FILE--
<?php
$arch1 = RarArchive::open(dirname(__FILE__) . "/store_method.rar");
$arch2 = RarArchive::open(dirname(__FILE__) . "/solid.rar");
echo "$arch1: " . ($arch1->isSolid()?'yes':'no') ."\n";
echo "$arch2: " . (rar_solid_is($arch2)?'yes':'no') . "\n";

$arch2->close();
var_dump(rar_solid_is($arch2));

echo "\n";
echo "Done.\n";
--EXPECTF--
RAR Archive "%sstore_method.rar": no
RAR Archive "%ssolid.rar": yes

Warning: rar_solid_is(): The archive is already closed in %s on line %d
bool(false)

Done.
