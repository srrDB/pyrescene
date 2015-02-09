--TEST--
Traversal of volume with only an archive continue from last volume
--SKIPIF--
<?php if(!extension_loaded("rar")) print "skip"; ?>
--FILE--
<?php

$f = dirname(__FILE__) . "/garbage.part03.rar";

echo "Traversal with rar_list:\n";
$a = RarArchive::open($f);
var_dump(rar_list($a));

echo "Traversal with rar_list (again with the same object):\n";
var_dump(rar_list($a));

echo "\nTraversal with foreach:\n";
$a = RarArchive::open($f);
foreach ($a as $e) {
	die("should not get here");
}
echo "Success.\n";

echo "\nUsage of RarArchive::getEntry:\n";
$a = RarArchive::open($f);
var_dump($a->getEntry("garbage.txt"));

echo "\nUsage of directory stream:\n";
$it = new DirectoryIterator("rar://" . rawurlencode($f));
foreach ($it as $e) {
	die("should not get here");
}
echo "Success.\n";

echo "\nUsage of static url stat:\n";
stat("rar://" . rawurlencode($f) . "#not_there");
echo "Success.\n";

echo "\n";
echo "Done.\n";
--EXPECTF--
Traversal with rar_list:
array(0) {
}
Traversal with rar_list (again with the same object):
array(0) {
}

Traversal with foreach:
Success.

Usage of RarArchive::getEntry:

Warning: RarArchive::getEntry(): cannot find file "garbage.txt" in Rar archive "%sgarbage.part03.rar" in %s on line %d
bool(false)

Usage of directory stream:
Success.

Usage of static url stat:

Warning: stat(): Found no entry not_there in archive %sgarbage.part03.rar in %s on line %d

Warning: stat(): stat failed for rar://%sgarbage.part03.rar#not_there in %s on line %d
Success.

Done.
