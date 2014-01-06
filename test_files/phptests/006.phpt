--TEST--
RarEntry::getCrc() method in multi-volume archives (PECL bug #9470)
--SKIPIF--
<?php if(!extension_loaded("rar")) print "skip"; ?>
--FILE--
<?php

$rar_file1 = rar_open(dirname(__FILE__).'/multi.part1.rar'); 
$list = rar_list($rar_file1);
echo $list[0]->getCrc()."\n";
echo $list[1]->getCrc()."\n";
echo $list[2]->getCrc()."\n";
echo "\n";

echo "Done\n";
?>
--EXPECTF--
52b28202
f2c79881
bcbce32e

Done
