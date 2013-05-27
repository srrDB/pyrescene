--TEST--
Access RAR archive with missing volumes
--SKIPIF--
<?php if(!extension_loaded("rar")) print "skip"; ?>
--FILE--
<?php
$rarF = RarArchive::open(dirname(__FILE__) . '/multi_broken.part1.rar');
var_dump(rar_list($rarF));
echo "Done.\n";
--EXPECTF--
Warning: rar_list(): Volume %smulti_broken.part2.rar was not found in %s on line %d

Warning: rar_list(): ERAR_EOPEN (file open error) in %s on line %d
bool(false)
Done.
