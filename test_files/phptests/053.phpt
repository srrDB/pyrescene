--TEST--
Stream wrapper malformed url
--SKIPIF--
<?php
if(!extension_loaded("rar")) die("skip");
--FILE--
<?php

echo "Test empty:\n";
$stream = fopen("rar://", "r");

echo "\nTest no fragment:\n";
$stream = fopen("rar://file.rar", "r");

echo "\nTest empty fragment:\n";
$stream = fopen("rar://file.rar#", "r");

echo "\nTest no path:\n";

$stream = fopen("rar://#frag", "r");

echo "\nTest no path and empty fragment:\n";

$stream = fopen("rar://#", "r");

echo "Done.\n";
--EXPECTF--
Test empty:

Warning: fopen(rar://): failed to open stream: The url must contain a path and a non-empty fragment; it must be in the form "rar://<urlencoded path to RAR archive>[*]#<urlencoded entry name>" in %s on line %d

Test no fragment:

Warning: fopen(rar://file.rar): failed to open stream: The url must contain a path and a non-empty fragment; it must be in the form "rar://<urlencoded path to RAR archive>[*]#<urlencoded entry name>" in %s on line %d

Test empty fragment:

Warning: fopen(rar://file.rar#): failed to open stream: The url must contain a path and a non-empty fragment; it must be in the form "rar://<urlencoded path to RAR archive>[*]#<urlencoded entry name>" in %s on line %d

Test no path:

Warning: fopen(rar://#frag): failed to open stream: The url must contain a path and a non-empty fragment; it must be in the form "rar://<urlencoded path to RAR archive>[*]#<urlencoded entry name>" in %s on line %d

Test no path and empty fragment:

Warning: fopen(rar://#): failed to open stream: The url must contain a path and a non-empty fragment; it must be in the form "rar://<urlencoded path to RAR archive>[*]#<urlencoded entry name>" in %s on line %d
Done.
