--TEST--
RarArchive::open() volume callback long return (case MAXPATHLEN <= NM)
--SKIPIF--
<?php
if(!extension_loaded("rar")) die("skip");
if (!defined("PHP_MAXPATHLEN"))
	define("PHP_MAXPATHLEN", RAR_MAXPATHLEN);
if (!(PHP_MAXPATHLEN <= 1024))
	die("skip; this test is for systems where MAXPATHLEN <= 1024");
--FILE--
<?php
if (!defined("PHP_MAXPATHLEN"))
	define("PHP_MAXPATHLEN", RAR_MAXPATHLEN);

$fn = dirname(__FILE__) . '/multi_broken.part1.rar';
	
function testA($vol) { if ($vol[0] != 'a') return str_repeat("a", PHP_MAXPATHLEN); }
$rar = RarArchive::open($fn, null, 'testA');
$rar->getEntries();

echo "Done.\n";
--EXPECTF--
Warning: RarArchive::getEntries(): Cound not expand filename aaaa%s in %s on line %d

Warning: RarArchive::getEntries(): ERAR_EOPEN (file open error) in %s on line %d
Done.
