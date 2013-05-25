--TEST--
RarArchive direct instantiation does not crash
--SKIPIF--
<?php if(!extension_loaded("rar")) die("skip");
--FILE--
<?php

new RarArchive();

echo "Done\n";
--EXPECTF--
Fatal error: Call to private RarArchive::__construct() from invalid context in %s on line %d
