--TEST--
RarArchive::getComment() basic test
--SKIPIF--
<?php if(!extension_loaded("rar")) print "skip"; ?>
--FILE--
<?php
$rar_arch = RarArchive::open(dirname(__FILE__) . '/commented.rar'); 
echo $rar_arch->getComment();
echo "\n";
echo "Done\n";
--EXPECTF--
This is the comment of the file commented.rar.
Done
