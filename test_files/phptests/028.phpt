--TEST--
RarArchive::open() basic test
--SKIPIF--
<?php if(!extension_loaded("rar")) print "skip"; ?>
--FILE--
<?php
$arch = RarArchive::open(dirname(__FILE__) . "/dirlink_unix.rar");
var_dump(get_class($arch));


echo "Done\n";
--EXPECTF--
string(10) "RarArchive"
Done
