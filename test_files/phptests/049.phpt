--TEST--
RarArchive::open() volume callback long return (case MAXPATHLEN > NM)
--SKIPIF--
<?php
if(!extension_loaded("rar")) die("skip");
if (!defined("PHP_MAXPATHLEN"))
	define("PHP_MAXPATHLEN", RAR_MAXPATHLEN);
if (!(PHP_MAXPATHLEN > 1024))
	die("skip test is for systems where MAXPATHLEN > 1024");
$rp = dirname(__FILE__) . "/" . str_repeat("a", 1024);
if (strlen(dirname(__FILE__) > PHP_MAXPATHLEN - 1))
	die("skip current directory is too deep.");
--FILE--
<?php
if (!defined("PHP_MAXPATHLEN"))
	define("PHP_MAXPATHLEN", RAR_MAXPATHLEN);

chdir(dirname(__FILE__));
$fn = dirname(__FILE__) . '/multi_broken.part1.rar';
	
function testA($vol) { if ($vol[0] != 'a') return str_repeat("a", 1024); }
$rar = RarArchive::open($fn, null, 'testA');
$rar->getEntries();

echo "Done.\n";
--EXPECTF--
Warning: RarArchive::getEntries(): Resolved path is too big for the unRAR library in %s on line %d

Warning: RarArchive::getEntries(): ERAR_EOPEN (file open error) in %s on line %d
Done.
