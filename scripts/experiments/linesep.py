"""
You have \r\n, \r and \n as most common lineseps nowadays: 
http://en.wikipedia.org/wiki/Newline
If there was a script that (badly) fixed it to \n\r instead of \r\n, 
there is still only one line in notepad.exe, thus not noticing problems.
An other script will fail on that and introduces a new line \n\r\n 
by fixing it because the line ends on the old \r standard.
Who would keep such a script running, knowing it did all that?
The second script was probably an FTP client that transferred .nfo files 
in ascii mode while racing.
"""

if __name__ == '__main__':
    testfile = "linesep_test.txt"
    with open(testfile, 'w') as ofile:
        for _ in range(10):
            ofile.writelines("A line with r n.\r\n")
        for _ in range(10):
            ofile.writelines("A line with n r.\n\r")
        for _ in range(10):
            ofile.writelines("A line with n r n.\n\r\n")
    print("Done!")