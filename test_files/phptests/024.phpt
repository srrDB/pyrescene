--TEST--
rar_open()/RarEntry::getStream() (headers level password)
--SKIPIF--
<?php if(!extension_loaded("rar")) print "skip"; ?>
--FILE--
<?php
echo "--> should fail (no password):\n";
$rar_file1 = rar_open(dirname(__FILE__).'/encrypted_headers.rar');
$entries = rar_list($rar_file1);

echo "\n--> should fail (wrong password):\n";
$rar_file1 = rar_open(dirname(__FILE__).'/encrypted_headers.rar', 'wrongpassword');
$entries = rar_list($rar_file1);

echo "\n--> should work:\n";
$rar_file2 = rar_open(dirname(__FILE__).'/encrypted_headers.rar', 'samplepassword');
$entries = rar_list($rar_file2);

echo "Found " . count($entries) . " files.\n";
echo "Content of first one follows:\n";
//reset($entries)->extract(false, "./temp.txt");
$stream = reset($entries)->getStream();
var_dump($stream);
if ($stream !== FALSE) {
	while (!feof($stream)) {
		echo fread($stream, 128);
	}
}
echo "\n";

echo "Done\n";
--EXPECTF--
--> should fail (no password):

Warning: rar_list(): ERAR_MISSING_PASSWORD (password needed but not specified) in %s on line %d

--> should fail (wrong password):

Warning: rar_list(): ERAR_BAD_DATA in %s on line %d

--> should work:
Found 2 files.
Content of first one follows:
resource(%d) of type (stream)
Encrypted file 1 contents.
Done
