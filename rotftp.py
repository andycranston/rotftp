#! /usr/bin/python3
#
# @(!--#) @(#) rotftp2.py, version 001, 23-august-2018
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

import os
import sys
import argparse
import socket

##############################################################################

#
# constants
#

MAX_PACKET_SIZE = 65536

##############################################################################

#
# globals
#

DEFAULT_DIRECTORY = "C:\\tftpboot"
DEFAULT_BLOCKSIZE = 512

##############################################################################

def showpacket(bytes):
    bpr = 10              # bpr is Bytes Per Row
    numbytes = len(bytes)

    if numbytes == 0:
        print("<empty packet>")
    else:
        i = 0
        while i < numbytes:
            if (i % bpr) == 0:
                print("{:04d} :".format(i), sep='', end='')
            
            c = bytes[i]
            
            if (c < 32) or (c > 126):
                c = '?'
            else:
                c = chr(c)

            print(" {:02X} {} ".format(bytes[i], c), sep='', end='')

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

def unpackreadrequestdata(readrequestdata):
    blocksize = 512
    
    if len(readrequestdata) == 0:
        return "badly formed read request data - no data bytes", "", blocksize, []
    
    if readrequestdata[-1] != 0:
        return "badly formed read request data - last byte not zero", "", blocksize, []
    
    datafields = readrequestdata.split(b'\x00')
    
    numdatafields = len(datafields)
    
    numdatafields -= 1            # throw away the null data field always at the end
    
    print("NUMDATA FIELDS: {}".format(numdatafields))
    
    if numdatafields == 0:
        return "badly formed read request data - no data", "", blocksize, []
    
    if (numdatafields % 2) != 0:
        return "badly formed read request data - odd number of data fields", "", blocksize, []

    filename = datafields[0].decode("utf-8")

    filename = filename.replace('/', '\\')
    
    if filename[0] == '\\':
        filename = filename[1:]

    mode     = datafields[1].decode("utf-8")
    
    if mode != "octet":
        return "only binary (octet) transfer are supported by this TFTP server implementation", "", blocksize, []
    
    options = []
    i = 2
    while (i < numdatafields):
        optionname = datafields[i].decode("utf-8")
        optionvalue = datafields[i+1].decode("utf-8")
        
        # some TFP clients use "timeout" instead of interval - hack round it here!!!
        if optionname == "timeout":
            optionname = "interval"
                
        if optionname == "blksize":
            try:
                blocksize = int(optionvalue)
            except ValueError:
                return "block size \"{}\" is not a valid integer string".format(optionvalue), "", blocksize, []
        elif optionname == "interval":
            try:
                interval = int(optionvalue)
            except ValueError:
                return "interval \"{}\" is not a valid integer string".format(optionvalue), "", blocksize, []
        elif optionname == "tsize":
            try:
                tsize = int(optionvalue)
            except ValueError:
                return "tsize \"{}\" is not a valid integer string".format(optionvalue), "", blocksize, []
        else:
            return "unsupported option \"{}\"".format(optionname), "", blocksize, []

        options.append("{}:{}".format(optionname, optionvalue))
        
        i += 2
    
    return "", filename, blocksize, options

##############################################################################

def sendoptionack(sock, clientip, clientport, options, filesize):

    packet = bytearray(MAX_PACKET_SIZE)

    packet[0] = 0              # option acknowledgement opcode
    packet[1] = 6

    i = 2
    
    for opt in options:
        pair = opt.split(':')
        
        optname = pair[0]
        optvalue = pair[1]
        
        if optname == "tsize":
            optvalue = str(filesize)
        
        for c in optname:
            packet[i] = ord(c)
            i += 1
        packet[i] = 0
        i += 1
        
        for c in optvalue:
            packet[i] = ord(c)
            i += 1
        packet[i] = 0
        i += 1
        
    ### showpacket(packet[0:i])
        
    sock.sendto(packet[0:i], (clientip, clientport))

##############################################################################

def readblock(filehandle, filesize, blocksize, blocknumber):
    numblocksinfile = filesize // blocksize + 1
    sizelastblock = filesize - (filesize // blocksize)

    filehandle.seek((blocknumber - 1) * blocksize)
    
    if blocknumber != numblocksinfile:
        databytes = filehandle.read(blocksize)
    elif sizelastblock > 0:
        databytes = filehandle.read(sizelastblock)
    else:
        databytes = bytes(0)
    
    return databytes

##############################################################################

def senddatablock(sock, clientip, clientport, blocknumber, databytes):
    numdatabytes = len(databytes)

    packet = bytearray(4 + numdatabytes)

    packet[0] = 0              # option acknowledgement opcode
    packet[1] = 3
    packet[2] = blocknumber // 256
    packet[3] = blocknumber %  256

    i = 4
    while numdatabytes > 0:
        packet[i] = databytes[i-4]
        i += 1
        numdatabytes -= 1

    ### showpacket(packet)
        
    sock.sendto(packet, (clientip, clientport))

##############################################################################

#
# Main code
#

def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--dir",  help="initial directory to change to", default=DEFAULT_DIRECTORY)

    args = parser.parse_args()

    initdir = args.dir

    try:
        os.chdir(initdir)
    except OSError:
        print("{}: unable to change to initial directory \"{}\"".format(progname, initdir), file=sys.stderr)
        sys.exit(2)

    # create a TCP/IP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    # bind the socket to the port
    sock.bind(('', 69))
    
    # main loop for DHCP server
    while True:
        print("Waiting for a TFTP packet")

        try:
            tftppacket, address = sock.recvfrom(MAX_PACKET_SIZE)
        except ConnectionResetError:
            print("{}: connecton reset error - going again".format(progname), file=sys.stderr)
            continue
            
        clientip = address[0]
        clientport = address[1]
        packetlength = len(tftppacket)

        if packetlength < 4:
            print("{}: packet length too short - ignoring".format(progname), file=sys.stderr)
            showpacket(tftppacket)
            continue

        opcode = (tftppacket[0] * 256) + tftppacket[1]

        # show the packet
        print("IP: {}   Port: {}   Opcode: {}   Length: {}".format(clientip, clientport, opcode, packetlength))
        ### showpacket(tftppacket)
        
        fileopen = False

        ###############################################################################
        # opcode 1 - read request                                                     #
        ###############################################################################
        if opcode == 1:
            errmsg, filename, blocksize, options = unpackreadrequestdata(tftppacket[2:])
            if errmsg != "":
                senderrormessage(sock, clientip, clientport, 0, errmsg)
                continue
                
            try:
                filesize = os.path.getsize(filename)
            except FileNotFoundError:
                senderrormessage(sock, clientip, clientport, 1, "file \"{}\" not found".format(filename))
                continue
            
            try:
                filehandle = open(filename, "rb")
            except FileNotFoundError:
                senderrormessage(sock, clientip, clientport, 1, "file \"{}\" not found".format(filename))
                continue
                            
            print("Filename: {}   Size: {}    Block size: {}".format(filename, filesize, blocksize))

            fileopen = True
            
            if len(options) > 0:
                sendoptionack(sock, clientip, clientport, options, filesize)
                continue;
                
            print("Should send first data block - block size={}".format(blocksize))
            databytes = readblock(filehandle, filesize, blocksize, 1)
            senddatablock(sock, clientip, clientport, 1, databytes)

        ###############################################################################
        # opcode 2 - write reqrest                                                    #
        ###############################################################################
        elif opcode == 2:
            senderrormessage(sock, clientip, clientport, 0, "write request opcode 2 not supported")

        ###############################################################################
        # opcode 3 - data                                                             #
        ###############################################################################
        elif opcode == 3:
            print("{}: received data block - should not be possible for a read only TFTP server", file=sys.stderr)

        ###############################################################################
        # opcode 4 - acknowledgement                                                  #
        ###############################################################################
        elif opcode == 4:
            block = (tftppacket[2] * 256) + tftppacket[3]
            
            if block == 0:
                print("Should send first data block as option ack receieved ok - blocksize={}".format(blocksize))
                databytes = readblock(filehandle, filesize, blocksize, 1)
                senddatablock(sock, clientip, clientport, 1, databytes)
            else:
                numblocksinfile = filesize // blocksize + 1
                if block != numblocksinfile:
                    databytes = readblock(filehandle, filesize, blocksize, block + 1)
                    senddatablock(sock, clientip, clientport, block + 1, databytes)
                    
        ###############################################################################
        # opcode 5 - error message from client                                        #
        ###############################################################################
        elif opcode == 5:
            errornumber = (tftppacket[2] * 256) + tftppacket[3]
            errormessage = "error text not present in packet data"
            
            if len(tftppacket) > 4:
                strings = tftppacket[4:].split(b'\x00')
                
                if len(strings) >= 1:
                    errormessage = strings[0].decode("utf-8")
            
            print("Error code {} from client - message reads: {}".format(errornumber, errormessage))

        ###############################################################################
        # opcode 6 - option acknowledgement                                           #
        ###############################################################################
        elif opcode == 6:
            print("{}: received option acknowledgement - should not be possible for a read only TFTP server", file=sys.stderr)

        ###############################################################################
        # opcode unknown                                                              #
        ###############################################################################
        else:
            senderrormessage(sock, clientip, clientport, 0, "unexpected packet with opcode {} during idle state".format(opcode))
        
##########################################################################

progname = os.path.basename(sys.argv[0])

sys.exit(main())

# end of file
