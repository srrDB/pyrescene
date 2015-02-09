--TEST--
rar_open() non-existent archive with exceptions
--SKIPIF--
<?php if(!extension_loaded("rar")) print "skip"; ?>
--FILE--
<?php
RarException::setUsingExceptions(true);
try {
	$arch = RarArchive::open(dirname(__FILE__) . "/nonexistentarchive.rar");
} catch (RarException $re) {
	echo "Message: " . $re->getMessage()."\n";
	echo "Code: " . $re->getCode() ."\n";
}
echo "Done.\n";
--EXPECTF--
Message: unRAR internal error: Failed to open %snonexistentarchive.rar: ERAR_EOPEN (file open error)
Code: 15
Done.
