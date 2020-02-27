# rotftp

A one binary file transfer at a time read only TFTP server in Python 3.

The `rotftp` TFTP server is a cut back implementation which only allows
GET (i.e. readonly) operations and the transfers must be requested in binary.

This is for Windows users who may need to run up a TFTP server for a short while
such as PXE booting a client for a network install.  Also the handy `--dir` command
line option lets to easily point to a different directory to serve up
different files.

## Limitations

Remember the limitations of `rotftp` are:

* Only binary transfers allowed
* Only readonly - i.e. GET transfers allowed
* Only one transfer at a time

## Running the server

Make sure you have administrator rights to access well known TCP/IP port number
69 and that this port is open for inbound and outbound UDP packets on the
network interface you will use.

Create the following directory:

```
C:\tftpboot
```

Copy any required files into this directory that your TFTP clients will want to `GET`.

From a command window type the following command:

```
python rotftp.py
```

The `rotftp` TFTP server will now wait for requests.  From a TFTP client issue a `GET`
request for a file you have copied to the `C:\tftpboot` directory.  If everything is
working the file will transfer.

If you get an error make sure the request was made in binary mode as that is all
the `rotftp` server supports.

## Specifying a different directory

If the files you want to serve are in a different directory
to `C:\tftpboot` then use the `--dir` command
line switch to specify the directory.  For example if the files are in directory
`C:\ISO\OpenBSD\pxe` then run the server as follows:

```
python rotftp.py --dir C:\ISO\OpenBSD\pxe
```

## Stopping the `rotftp` server

From the command window use the Ctrl+Break keyboard sequence.  Just typing Ctrl+C
will not work.

## Credits

I could not have tested and debugged this code without the excellent
Windows command line TFTP client program available from
WinAgents Software Group here:

[WinAgents TFTP Client](http://www.winagents.com/en/products/tftp-client/index.php)

Also various pages from the TCP/IP Guide explain the TFTP protocol and
packet formats in more than enough detail:

[Trvial File Transfer Protocol (TFTP)](http://www.tcpipguide.com/free/t_TrivialFileTransferProtocolTFTP.htm)

---------------------------------------------------------------

End of README.md
