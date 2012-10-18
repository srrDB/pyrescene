--TEST--
Stream wrapper with header or file level passwords
--SKIPIF--
<?php
if(!extension_loaded("rar")) die("skip");
--FILE--
<?php

echo "Headers: should not work (no password):\n";
$stream = fopen("rar://" .
	dirname(__FILE__) . '/encrypted_headers.rar' .
	"#encfile1.txt", "r");

	
echo "\nHeaders: should not work (password given was file_password):\n";

$stream = fopen("rar://" .
	dirname(__FILE__) . '/encrypted_headers.rar' .
	"#encfile1.txt", "r", false,
	stream_context_create(array('rar'=>array('file_password'=>'samplepassword'))));
	
echo "\nHeaders: should work (password given was open_password):\n";

$stream = fopen("rar://" .
	dirname(__FILE__) . '/encrypted_headers.rar' .
	"#encfile1.txt", "r", false,
	stream_context_create(array('rar'=>array('open_password'=>'samplepassword'))));
var_dump(stream_get_contents($stream));

//////////////////////

echo "\n\nFiles: should not work (no password):\n";
$stream = fopen("rar://" .
	dirname(__FILE__) . '/encrypted_only_files.rar' .
	"#encfile1.txt", "r");

	
echo "\nFiles: should not work (password given was open_password):\n";

$stream = fopen("rar://" .
	dirname(__FILE__) . '/encrypted_only_files.rar' .
	"#encfile1.txt", "r", false,
	stream_context_create(array('rar'=>array('open_password'=>'samplepassword'))));
	
echo "\nFiles: should work (password given was file_password):\n";

$stream = fopen("rar://" .
	dirname(__FILE__) . '/encrypted_only_files.rar' .
	"#encfile1.txt", "r", false,
	stream_context_create(array('rar'=>array('file_password'=>'samplepassword'))));
var_dump(stream_get_contents($stream));

echo "\nDone.\n";

--EXPECTF--
Headers: should not work (no password):

Warning: fopen(rar://%sencrypted_headers.rar#encfile1.txt): failed to open stream: Error opening RAR archive %sencrypted_headers.rar: ERAR_MISSING_PASSWORD (password needed but not specified) in %s on line %d

Headers: should not work (password given was file_password):

Warning: fopen(rar://%sencrypted_headers.rar#encfile1.txt): failed to open stream: Error opening RAR archive %sencrypted_headers.rar: ERAR_MISSING_PASSWORD (password needed but not specified) in %s on line %d

Headers: should work (password given was open_password):
string(26) "Encrypted file 1 contents."


Files: should not work (no password):

Warning: fopen(rar://%sencrypted_only_files.rar#encfile1.txt): failed to open stream: Error opening file encfile1.txt inside RAR archive %sencrypted_only_files.rar: ERAR_MISSING_PASSWORD (password needed but not specified) in %s on line %d

Files: should not work (password given was open_password):

Warning: fopen(rar://%sencrypted_only_files.rar#encfile1.txt): failed to open stream: Error opening file encfile1.txt inside RAR archive %sencrypted_only_files.rar: ERAR_MISSING_PASSWORD (password needed but not specified) in %s on line %d

Files: should work (password given was file_password):
string(26) "Encrypted file 1 contents."

Done.
