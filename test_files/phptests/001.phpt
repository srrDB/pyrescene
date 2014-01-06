--TEST--
rar_open() function
--SKIPIF--
<?php if(!extension_loaded("rar")) print "skip"; ?>
--FILE--
<?php

$rar_file1 = rar_open(dirname(__FILE__).'/linux_rar.rar'); 
var_dump($rar_file1);

$rar_file2 = rar_open(dirname(__FILE__).'/latest_winrar.rar'); 
var_dump($rar_file2);

$rar_file3 = rar_open(dirname(__FILE__).'/no_such_file.rar'); 
var_dump($rar_file3);

echo "Done\n";
?>
--EXPECTF--
object(RarArchive)#%d (%d) {
}
object(RarArchive)#%d (%d) {
}

Warning: rar_open(): Failed to open %sno_such_file.rar: ERAR_EOPEN (file open error) in %s on line %d
bool(false)
Done
