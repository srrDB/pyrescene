--TEST--
RarEntry::extract() process extended (Windows)
--SKIPIF--
<?php if(!extension_loaded("rar")) die("skip");
die("skip test is not working under run-tests");
if (PHP_OS != 'WINNT') die("skip test for Windows NT");
exec('cacls ' . escapeshellarg(dirname(__FILE__)), $perms);
function concat($a,$b) { return $a.$b; }
$perms = array_reduce($perms, 'concat');
if (preg_match('/.* Everyone:\\(OI\\)\\(CI\\)F/i', $perms))
	die("skip directory has permissions that conflict with this test");
?>
--CLEAN--
@rmdir(dirname(__FILE__).'/temp_directory');
--FILE--
<?php
$fn1 = dirname(__FILE__) . '/dirs_and_extra_headers.rar';
$dest = dirname(__FILE__).'/temp_directory';
function concat($a,$b) { return $a.$b; }

@rmdir($dest);

echo "--> should have default permissions:\n";
$rarF = RarArchive::open($fn1);
$t = $rarF->getEntry('allow_everyone_ni');
$t->extract(false, $dest, NULL);
exec('cacls ' . escapeshellarg($dest), $perms);
$perms = array_reduce($perms, 'concat');
var_dump(preg_match('/.* Everyone:\\(OI\\)\\(CI\\)F/i', $perms));
@rmdir($dest);
echo "\n";

echo "--> should have permissions for everyone:\n";
$rarF = RarArchive::open($fn1);
$t = $rarF->getEntry('allow_everyone_ni');
$t->extract(false, $dest, NULL, true);
exec('cacls ' . escapeshellarg($dest), $perms);
$perms = array_reduce($perms, 'concat');
var_dump(preg_match('/.* Everyone:\\(OI\\)\\(CI\\)F/i', $perms));
echo "\n";
@rmdir($dest);

echo "Done\n";
--EXPECTF--
--> should have default permissions:
int(0)

--> should have permissions for everyone:
int(1)

Done
