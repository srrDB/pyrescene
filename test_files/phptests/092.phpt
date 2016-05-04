--TEST--
RarArchive::setAllowBroken has the desired effect
--SKIPIF--
<?php if(!extension_loaded("rar")) print "skip"; ?>
--FILE--
<?php

function retnull() { return null; }
$b = dirname(__FILE__) . "/multi_broken.part1.rar";

echo "* broken file; bad arguments\n";
$a = RarArchive::open($b, null, 'retnull');
$a->setAllowBroken();
rar_allow_broken_set($a);

echo "\n* broken file; do not allow broken (default)\n";
$a = RarArchive::open($b, null, 'retnull');
var_dump($a->getEntries());
var_dump(count($a));

echo "\n* broken file; do not allow broken (explicit)\n";
$a = RarArchive::open($b, null, 'retnull');
$a->setAllowBroken(false);
var_dump($a->getEntries());
var_dump(count($a));

echo "\n* broken file; allow broken\n";
$a = RarArchive::open($b, null, 'retnull');
$a->setAllowBroken(true);
foreach ($a->getEntries() as $e) {
	echo "$e\n";
}
var_dump(count($a));

echo "\n* broken file; allow broken; non OOP\n";
$a = RarArchive::open($b, null, 'retnull');
rar_allow_broken_set($a, true);
foreach ($a->getEntries() as $e) {
	echo "$e\n";
}
var_dump(count($a));

echo "\n";
echo "Done.\n";
--EXPECTF--
* broken file; bad arguments

Warning: RarArchive::setAllowBroken() expects exactly 1 parameter, 0 given in %s on line %d

Warning: rar_allow_broken_set() expects exactly 2 parameters, 1 given in %s on line %d

* broken file; do not allow broken (default)

Warning: RarArchive::getEntries(): ERAR_EOPEN (file open error) in %s on line %d
bool(false)

Warning: count(): ERAR_EOPEN (file open error) in %s on line %d
int(0)

* broken file; do not allow broken (explicit)

Warning: RarArchive::getEntries(): ERAR_EOPEN (file open error) in %s on line %d
bool(false)

Warning: count(): ERAR_EOPEN (file open error) in %s on line %d
int(0)

* broken file; allow broken
RarEntry for file "file1.txt" (52b28202)
int(1)

* broken file; allow broken; non OOP
RarEntry for file "file1.txt" (52b28202)
int(1)

Done.
