--TEST--
rar_close is called twice
--SKIPIF--
<?php if(!extension_loaded("rar")) print "skip"; ?>
--FILE--
<?php

$f1 = dirname(__FILE__) . "/latest_winrar.rar";
$a = RarArchive::open($f1);

echo $a."\n";

$a->close();
echo $a."\n";

$a->close();
echo $a."\n";

echo "\n";
echo "Done.\n";
--EXPECTF--
RAR Archive "%slatest_winrar.rar"
RAR Archive "%slatest_winrar.rar" (closed)

Warning: RarArchive::close(): The archive is already closed in %s on line %d
RAR Archive "%slatest_winrar.rar" (closed)

Done.
