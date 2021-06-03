# from https://stackoverflow.com/questions/36500197/how-to-get-time-from-an-ntp-server

import socket
import struct
import time

def RequestTimefromNtp(addr='pool.ntp.org'):
    # returns the time in seconds
    REF_TIME_1970 = 2208988800  # Reference time
    client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    data = b'\x1b' + 47 * b'\0'
    client.sendto(data, (addr, 123))
    data, address = client.recvfrom(1024)
    if data:
        t = struct.unpack('!12I', data)[10]
        t -= REF_TIME_1970
    return t

if __name__ == "__main__":
    t = RequestTimefromNtp()
    local_time = time.localtime(t)
    print(time.strftime("%Y/%m/%d %H:%M:%S", local_time))
