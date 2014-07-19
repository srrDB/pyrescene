--TEST--
rar_entry_get() non-existent file with exceptions
--SKIPIF--
<?php if(!extension_loaded("rar")) print "skip"; ?>
--FILE--
<?php
RarException::setUsingExceptions(true);
$arch = RarArchive::open(dirname(__FILE__) . "/latest_winrar.rar");
try {
	$arch->getEntry('nonexistentfile.txt');
} catch (RarException $re) {
	echo "Message: " . $re->getMessage()."\n";
	echo "Code: " . $re->getCode() ."\n";
}
echo "Done.\n";
--EXPECTF--
Message: cannot find file "nonexistentfile.txt" in Rar archive "%slatest_winrar.rar"
Code: -1
Done.
