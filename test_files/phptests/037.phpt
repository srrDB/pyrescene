--TEST--
RarEntry::getStream(), password not given, with exceptions
--SKIPIF--
<?php if(!extension_loaded("rar")) print "skip"; ?>
--FILE--
<?php
RarException::setUsingExceptions(true);
echo "--> should fail (no password):\n";
$rar_file1 = rar_open(dirname(__FILE__).'/encrypted_only_files.rar');
$entries = rar_list($rar_file1);
var_dump(count($entries));
try {
	var_dump($entries[0]->getStream());
}  catch (RarException $re) {
	echo "Message: " . $re->getMessage()."\n";
	echo "Code: " . $re->getCode() ."\n";
}
echo "Done.\n";
--EXPECTF--
--> should fail (no password):
int(2)
Message: unRAR internal error: ERAR_MISSING_PASSWORD (password needed but not specified)
Code: 22
Done.
