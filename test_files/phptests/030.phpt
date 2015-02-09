--TEST--
RarArchive::getEntry() basic test
--SKIPIF--
<?php if(!extension_loaded("rar")) print "skip"; ?>
--FILE--
<?php
$rar_arch = RarArchive::open(dirname(__FILE__) . '/solid.rar');
$rar_entry = $rar_arch->getEntry('tese.txt');
echo $rar_entry;
echo "\n";
echo "Done\n";
--EXPECTF--
RarEntry for file "tese.txt" (23b93a7a)
Done
