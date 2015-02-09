--TEST--
rar_list et al. give consistent results if called twice
--SKIPIF--
<?php if(!extension_loaded("rar")) print "skip"; ?>
--FILE--
<?php

$f = dirname(__FILE__) . "/multi_broken.part1.rar";

echo "* rar_list():\n";
$a = RarArchive::open($f);
var_dump(rar_list($a));
var_dump(rar_list($a));

echo "\n* rar_entry_get():\n";
$a = RarArchive::open($f);
var_dump($a->getEntry("file1.txt"));
var_dump($a->getEntry("file1.txt"));

echo "\n* dimension access:\n";
$a = RarArchive::open($f);
var_dump($a[0]);
var_dump($a[0]);

echo "\n* foreach access:\n";
$a = RarArchive::open($f);
foreach ($a as $e) { echo "shouldn't happen: $e\n"; };
foreach ($a as $e) { echo "shouldn't happen: $e\n"; };

echo "\n* url stat:\n";
var_dump(stat("rar://".rawurlencode($f)."#file1.txt"));
var_dump(stat("rar://".rawurlencode($f)."#file1.txt"));
//no need to test directory open, _rar_get_cachable_rararch handles it too

echo "\n";
echo "Done.\n";
--EXPECTF--
* rar_list():

Warning: rar_list(): Volume %smulti_broken.part2.rar was not found in %s on line %d

Warning: rar_list(): ERAR_EOPEN (file open error) in %s on line %d
bool(false)

Warning: rar_list(): ERAR_EOPEN (file open error) in %s on line %d
bool(false)

* rar_entry_get():

Warning: RarArchive::getEntry(): Volume %smulti_broken.part2.rar was not found in %s on line %d

Warning: RarArchive::getEntry(): ERAR_EOPEN (file open error) in %s on line %d
bool(false)

Warning: RarArchive::getEntry(): ERAR_EOPEN (file open error) in %s on line %d
bool(false)

* dimension access:

Warning: main(): Volume %smulti_broken.part2.rar was not found in %s on line %d

Warning: main(): ERAR_EOPEN (file open error) in %s on line %d
NULL

Warning: main(): ERAR_EOPEN (file open error) in %s on line %d
NULL

* foreach access:

Warning: main(): Volume %smulti_broken.part2.rar was not found in %s on line %d

Warning: main(): ERAR_EOPEN (file open error) in %s on line %d

Warning: main(): ERAR_EOPEN (file open error) in %s on line %d

* url stat:

Warning: stat(): Volume %smulti_broken.part2.rar was not found in %s on line %d

Warning: stat(): Error reading entries of archive %smulti_broken.part1.rar: ERAR_EOPEN (file open error) in %s on line %d

Warning: stat(): stat failed for rar://%smulti_broken.part1.rar#file1.txt in %s on line %s
bool(false)

Warning: stat(): Volume %smulti_broken.part2.rar was not found in %s on line %d

Warning: stat(): Error reading entries of archive %smulti_broken.part1.rar: ERAR_EOPEN (file open error) in %s on line %d

Warning: stat(): stat failed for rar://%smulti_broken.part1.rar#file1.txt in %s on line %d
bool(false)

Done.