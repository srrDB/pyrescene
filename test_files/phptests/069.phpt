--TEST--
RarEntry direct instantiation does not crash
--SKIPIF--
<?php if(!extension_loaded("rar")) die("skip");
--FILE--
<?php

new RarEntry();

echo "Done\n";
--EXPECTF--
Fatal error: Call to private RarEntry::__construct() from invalid context in %s on line %d
