#! /usr/bin/python3
#
# @(!--#) @(#) rotftp.py, version 010, 15-february-2018
#
# a TFTP server that does read only transfers in binary (mode "octet")
#
# the server assumes a super reliable connection
# does basic option negotiation
#
# use Ctrl+Break instead of Ctrl^C to interrupt.
#

##############################################################################

#
# Help from:
# ---------
#
#    https://pymotw.com/2/socket/tcp.html
#    https://pymotw.com/2/socket/udp.html
#    http://www.tcpipguide.com/free/t_TrivialFileTransferProtocolTFTP.htm
#

#
# Packet format
# -------------
#
# Offset    Length   Notes
# ------    ------   -----
#
#   0-1     2        Operation code
#                    1 = Read Request
#                    2 = Write request
#                    3 = Data
#                    4 = Acknowledgment
#                    5 = Error
#                    6 = Option Acknowledgment
#

##############################################################################

#
# imports
#

import sys
import os
import socket

##############################################################################

#
# constants
#

DEFAULT_BLOCKSIZE = 512
MIN_OPCODE = 1
MAX_OPCODE = 6

##############################################################################

#
# globals
#

DEFAULT_BLOCK_SIZE = 512

##############################################################################

def showpacket(bytes):
    bpr = 16              # bpr is Bytes Per Row
    numbytes = len(bytes)

    if numbytes == 0:
        print("<empty packet>")
    else:
        i = 0
        while i < numbytes:
            if (i % bpr) == 0:
                print("{:04d} :".format(i), sep='', end='')

            print(" {:02X}".format(bytes[i]), sep='', end='')

            if ((i + 1) % bpr) == 0:
                print()

            i = i + 1

    if (numbytes % bpr) != 0:
        print()

##############################################################################

def senderrormessage(sock, clientip, clientport, errorcode, errormessage):
    if errormessage == "":
        errormessage = "An error has occurred"

    print(progname, ": ", errorcode, ": ", errormessage, sep='', file=sys.stderr)

    lenerrormessage = len(errormessage)

    packet = bytearray(5 + lenerrormessage)

    packet[0] = 0              # error message opcode
    packet[1] = 5

    packet[2] = 0              # error code
    packet[3] = errorcode

    i = 0
    while i < lenerrormessage:
        packet[4 + i] = ord(errormessage[i])
        i += 1

    packet[4 + lenerrormessage] = 0

    sock.sendto(packet, (clientip, clientport))

##############################################################################

def extractfilenameandmode(packetdata):
    if len(packetdata) < 4:
        return False, "", ""

    strings = packetdata.split(b'\x00')

    if len(strings) < 2:
        return False, "", ""

    filename = strings[0].decode("utf-8")
    mode = strings[1].decode("utf-8")

    if (len(filename) == 0) or (len(mode) == 0):
        return False, "", ""

    if (filename[0] == '/') or (filename[0] == '\\'):
        if len(filename) < 2:
            return False, "", ""
        else:
            filename = filename[1:]

    return True, filename, mode

##############################################################################

def isackblockzero(readrequest):
    if len(readrequest) != 4:
        return False

    if readrequest[0] != 0:
        return False
    if readrequest[1] != 4:
        return False
    if readrequest[2] != 0:
        return False
    if readrequest[0] != 0:
        return False

    return True

##############################################################################

def isackblock(readrequest):
    if len(readrequest) != 4:
        return False, 0

    if readrequest[0] != 0:
        return False, 0
    if readrequest[1] != 4:
        return False, 0

    blocknum = (readrequest[2] * 256) + readrequest[3]

    return True, blocknum

##############################################################################

#
# Main code
#

# extract program name
progname = os.path.basename(sys.argv[0])

# extract number of arguments (ignoring program name)
numargs = len(sys.argv) - 1

# if an odd number of arguments then something wrong
if (numargs % 2) != 0:
    print(progname, ": odd number of command line arguments", sep='', file=sys.stderr)
    sys.exit(1)

# set program defaults
initdir = ""

# loop through command line args
arg = 1
while arg < numargs:
    if sys.argv[arg] == "-d":
        initdir = sys.argv[arg+1]
    else:
        print(progname, ": unrecognised command line argument \"", sys.argv[arg], "\"", sep='', file=sys.stderr)
        sys.exit(1)
    arg = arg + 2

# if initial directorty specified then change to it
if initdir != "":
    try:
        os.chdir(initdir)
    except OSError:
        print(progname, ": unable to change to initial directory \"", initdir, "\"", sep='', file=sys.stderr)
        sys.exit(1)

# create a TCP/IP socket
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# bind the socket to the port
sock.bind(('', 69))

# main loop for DHCP server
while True:
    while True:
        # Wait for a read request
        print("")
        print("waiting for a TFTP read request")
        readrequest, address = sock.recvfrom(32768)
        clientip = address[0]
        clientport = address[1]

        # show the packet
        print("IP:", clientip, "  Port number:", clientport, "  Packet length:", len(readrequest))
        showpacket(readrequest)

        # if readrequest packet too short to determine opcode
        if len(readrequest) < 2:
            print(progname, ": received packet too short - ignoring", sep='', file=sys.stderr)
            continue

        # get opcode
        opcode = (readrequest[0] * 256) + readrequest[1]

        # check for invalid opcode
        if (opcode < MIN_OPCODE) or (opcode > MAX_OPCODE):
            print(progname, ": invalid opcode number ", opcode, " - ignoring", sep='', file=sys.stderr)
            continue

        # is this a read request?
        if opcode == 1:
            # yes, break out of the loop
            break

        # is this a write request?
        if opcode == 2:
            # yes, send custom error message
            senderrormessage(sock, clientip, clientport, 0, "write request not supported")
            continue

        # anything else is unexpected at this time
        senderrormessage(sock, clientip, clientport, 0, "unexpected packet")

    # got a read request - any packet less than 6 bytes is a non starter
    if len(readrequest) < 6:
        senderrormessage(sock, clientip, clientport, 0, "read request packet is too short")
        continue

    # lose the read request opcode
    readrequest = readrequest[2:]

    # the last byte should be 0
    if readrequest[-1] != 0:
        senderrormessage(sock, clientip, clientport, 0, "last byte of read request packet should be 0")
        continue

    # lose last byte
    readrequest = readrequest[:-1]

    # extract fields from read request
    fields = readrequest.split(b'\x00')

    # too few fields no good
    if len(fields) < 2:
        senderrormessage(sock, clientip, clientport, 0, "too few fields in read request")
        continue

    # if not a multiple of 2
    if (len(fields) % 2) != 0:
        senderrormessage(sock, clientip, clientport, 0, "odd number of fields in read request")
        continue

    # extract filename and mode
    filename = fields[0]
    mode = fields[1]

    # print filename and mode
    print("Filename and mode ...:", filename, mode)

    # remove any leading / character if present
    if len(filename) >= 2:
        if filename[0] == ord('/'):
            filename = filename[1:]
            print("Filename (no leading /) ...:", filename)

    # only mode octet allowed
    if mode != "octet".encode('ascii'):
        senderrormessage(sock, clientip, clientport, 0, "only octet transfers allowed")
        continue

    # does file exist
    if not os.path.exists(filename):
        senderrormessage(sock, clientip, clientport, 1, "file not found")
        continue

    # plain file?
    if not os.path.isfile(filename):
        senderrormessage(sock, clientip, clientport, 1, "file not a regular file")
        continue

    # open the file in binary mode
    try:
        file = open(filename, "rb")
    except OSError:
        senderrormessage(sock, clientip, clientport, 1, "cannot open file for binary reading")
        continue

    # get size of file
    filesize = os.path.getsize(filename)

    # show file size
    print("Size.......:", filesize)

    # set blocksize
    blocksize = DEFAULT_BLOCKSIZE

    # any options to deal with
    if len(fields) > 2:
        options = fields[2:]

        oack = bytearray(2)
        oack[0] = 0
        oack[1] = 6

        i = 0
        while i < len(options):
            optname = options[i]
            i += 1
            optvalue = options[i]
            i += 1

            if optname == "tsize".encode('ascii'):
                print("set tsize to", filesize)
                oack += "tsize".encode('ascii')
                oack += b'\x00'
                oack += ("{:d}".format(filesize)).encode('ascii')
                oack += b'\x00'

            if optname == "blksize".encode('ascii'):
                print("set blksize to", optvalue.decode('ascii'))
                oack += "blksize".encode('ascii')
                oack += b'\x00'
                oack += optvalue
                oack += b'\x00'
                blocksize = int(optvalue.decode('ascii'))

        print("sending option ack")
        showpacket(oack)
        sent = sock.sendto(oack, (clientip, clientport))

        # Wait for a read request
        print("wait for block #0 ack")
        readrequest, address = sock.recvfrom(32768)
        showpacket(readrequest)

        if isackblockzero(readrequest) != True:
            senderrormessage(sock, clientip, clientport, 1, "expecting ACK on block zero - resetting")
            file.close()
            continue
            
    # read data from file, send it and wait for acknowledgement
    blocknum = 1
    while True:
        chunk = file.read(blocksize)

        datablock = bytearray(4)

        datablock[0] = 0     # data block opcode
        datablock[1] = 3

        datablock[2] = blocknum // 256
        datablock[3] = blocknum % 256
        
        if len(chunk) > 0:
            datablock += chunk

        # send it
        print("sending data block", blocknum)
        # showpacket(datablock)
        sent = sock.sendto(datablock, (clientip, clientport))
        print("sent", sent, "bytes")

        # Wait for an acknowledgement
        print("")
        print("waiting for an acknowledgement to block", blocknum)
        readrequest, address = sock.recvfrom(32768)
        showpacket(readrequest)
        isack, bn = isackblock(readrequest)

        if len(readrequest) >= 2:
            if readrequest[1] == 5:
                print("OpenBSD style boot abort error code 3")
                break

        if isack != True:
            senderrormessage(sock, clientip, clientport, 1, "expectig ACK on block number - resetting")
            break

        print("block", blocknum, "ack'ed with block", bn)

        # end of file
        if len(chunk) < blocksize:
            print("finished sending - total of", blocknum, "blocks")
            break

        # increment bloc count and get next chunk
        blocknum += 1


    # if control gets here then file sent or an error - either way close the file
    file.close()

sys.exit(0)

# end of file
