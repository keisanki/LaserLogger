#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
"""Module to interface with Toptica laser systems"""

import socket

class DLCpro(object):
    """Abstraction class for Toptica DLCpro systems"""

    DEBUG = False

    def __init__(self, ip = None, port = 1998):
        """Initialization"""

        self.ip = ip
        self.port = port
        self.connected = False

        # prepare TCP/IP connection to device
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.socket.settimeout(1)

        if self.ip and self.port:
            try:
                self.socket.connect((self.ip, self.port))
                self.connected = True
            except:
                pass

        # discard welcome message
        self.readReply()

    def __del__(self):
        """Disconnects from the DLCpro on object deletion"""

        self.socket.close()

        if self.DEBUG:
            print("DLCpro object destroyed")

    def sendCmd(self, cmd):
        """Sends a command string to the DLCpro

        :param cmd: string to be sent
        :return: True on success
        """

        if not self.connected:
            return False

        if self.DEBUG:
            print(">>> {}".format(cmd))
        cmd += "\r\n"
        try:
            self.socket.sendall(cmd.encode())
        except socket.timeout:
            return False

        return True

    def readReply(self):
        """Reads a reply string from the DLCpro

        :return: Reply string or None
        """

        if not self.connected:
            return False

        reply = ""
        try:
            while (len(reply) < 2) or (reply[-2] != '>' or reply[-1] != ' '):
                reply += self.socket.recv(1024).decode("utf-8", "ignore")
        except socket.timeout:
            reply = ""
            if self.DEBUG:
                print("DPL32G._readReply() timeout")
        if self.DEBUG:
            print("<<< {}".format(reply))

        return reply

    def getParam(self, query):
        """Simplified frontend function to query for a single parameter

        :query: Parameter, e.g. laser1:dl:cc:current-act
        :return: parameter value as string or empty string
        """

        self.sendCmd("(param-disp '{})".format(query))
        reply = ""

        try:
            reply = self.readReply()
            reply = reply.split("\n", 1)[0]
            reply = reply.split(" = ")[1]
        except:
            pass

        return reply

if __name__ == '__main__':
    """Just testing"""
    DLC = DLCpro(ip="192.168.1.12", port=1998)

    print(DLC.getParam("laser1:dl:cc:current-act"))
    print(DLC.getParam("laser1:dl:pc:voltage-act"))
