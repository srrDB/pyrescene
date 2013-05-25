--TEST--
RarEntry::getStream() with Linux directories and links
--SKIPIF--
<?php if(!extension_loaded("rar")) print "skip"; ?>
--FILE--
<?php
$rar = rar_open(dirname(__FILE__) . "/dirlink_unix.rar");

echo "\nDirectory\n";

$e = rar_entry_get($rar, "nopermdir");
echo $e."\n";
echo "perms: " . decoct($e->getAttr() & 0x1FF) . "\n"; //no read/write/execute perms
echo "win directory bit: " . (($e->getAttr() & RarEntry::ATTRIBUTE_WIN_DIRECTORY) != 0) ."\n";
echo "unix directory attr: " . (($e->getAttr() & RarEntry::ATTRIBUTE_UNIX_FINAL_QUARTET)
	== RarEntry::ATTRIBUTE_UNIX_DIRECTORY) ."\n";
echo "unix symlink attr: " . (($e->getAttr() & RarEntry::ATTRIBUTE_UNIX_FINAL_QUARTET)
	== RarEntry::ATTRIBUTE_UNIX_SYM_LINK) ."\n";
$stream = $e->getStream();
$cont = stream_get_contents($stream);
echo "$cont (strlen() " . strlen($cont) . ")\n";

echo "\nLink\n";

$e = rar_entry_get($rar, "link");
echo $e."\n";
echo "perms: " . decoct($e->getAttr() & 0x1FF) . "\n";
echo "win directory bit: " . (($e->getAttr() & RarEntry::ATTRIBUTE_WIN_DIRECTORY) != 0) ."\n"; //coincidence
echo "unix directory attr: " . (($e->getAttr() & RarEntry::ATTRIBUTE_UNIX_FINAL_QUARTET)
	== RarEntry::ATTRIBUTE_UNIX_DIRECTORY) ."\n";
echo "unix symlink attr: " . (($e->getAttr() & RarEntry::ATTRIBUTE_UNIX_FINAL_QUARTET)
	== RarEntry::ATTRIBUTE_UNIX_SYM_LINK) ."\n";
$stream = $e->getStream();
$cont = stream_get_contents($stream);
echo "$cont (strlen() " . strlen($cont) . ")\n"; //varies on windows and linux

echo "Done\n";
--EXPECTF--
Directory
RarEntry for directory "nopermdir" (0)
perms: 0
win directory bit: 
unix directory attr: 1
unix symlink attr: 
 (strlen() 0)

Link
RarEntry for file "link" (43e55b49)
perms: 777
win directory bit: 1
unix directory attr: 
unix symlink attr: 1
%s
Done
