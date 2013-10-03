--TEST--
rar_open() function with a non-RAR
--SKIPIF--
<?php if(!extension_loaded("rar")) print "skip"; ?>
--FILE--
<?php

$rar_file1 = rar_open(dirname(__FILE__).'/rar_notrar.rar'); 
var_dump($rar_file1);
echo "\n";

echo "Done\n";
?>
--EXPECTF--
Warning: rar_open(): Failed to open %s: ERAR_BAD_ARCHIVE in %s on line %d
bool(false)

Done
