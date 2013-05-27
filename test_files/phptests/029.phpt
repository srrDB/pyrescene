--TEST--
RarArchive::getEntries() basic test
--SKIPIF--
<?php if(!extension_loaded("rar")) print "skip"; ?>
--FILE--
<?php
$arch = RarArchive::open(dirname(__FILE__) . "/dirlink_unix.rar");
foreach ($arch->getEntries() as $e) {
	echo $e . "\n";
}

echo "Done\n";
--EXPECTF--
RarEntry for file "emptydir%clink" (36ac99f1)
RarEntry for file "file" (b95e8411)
RarEntry for file "link" (43e55b49)
RarEntry for directory "emptydir" (0)
RarEntry for directory "nopermdir" (0)
RarEntry for directory "setuiddir" (0)
RarEntry for directory "stickydir" (0)
Done
