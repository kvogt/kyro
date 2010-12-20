#!/usr/bin/env python
import socket
import select
import time
import struct
import sys

PAYLOAD = 'x' * 184

class Pinger():
    
    def __init__(self):
        self.registered = {}
        self.sent = 0
        self.received = 0
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
        self.sock.setblocking(False)
        # Need massive socket receive buffer if concurrency is high
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1048576 * 2)
        
    def register(self, addr, id):
        addr = socket.gethostbyname(addr)
        if addr in self.registered:
            self.registered[addr].append(id)
        else:
            self.registered[addr] = [id]
        
    def callback(self, addr, id, seq, ms):
        print "%s (id=%s seq=%s ms=%.2f count=%s)" % (addr, id, seq, ms, self.received)
            
    def poll(self):
        sst = time.time()
        rlist, wlist, xlist = select.select([self.sock, sys.stdin], [], [], 0.0001)
        for sock in rlist:
            if sock == sys.stdin:
                line = sys.stdin.readline()
                if self.state = STATE_COMMAND:
                    line = line.strip().upper()
                    if line.startswith == 'PING':
                        # TODO: allow registration of pings' remotely
                        pass
            else:
                et = time.time()
                data, paddr = self.sock.recvfrom(256)
                paddr = paddr[0]
                icmpHeader = data[20:28]
                ptype, pcode, checksum, pid, pseq = struct.unpack(
                    "bbHHh", icmpHeader
                )
                for addr, ids in self.registered.items():
                    if pid in ids and paddr == addr:
                        tstamp = data[28:36]
                        [st] = struct.unpack("d", tstamp)
                        ms = (et - st) * 1000.0
                        self.callback(addr, pid, pseq, ms)
                        self.received += 1
                
    def checksum(self, data):
        byte_sum = sum([ord(data[i * 2]) + (ord(data[i * 2 + 1]) << 8) for i in range(len(data) / 2)])
        if len(data) % 2 == 1:
            byte_sum += ord(data[-1])
        byte_sum = byte_sum + (byte_sum >> 16)
        answer = ~byte_sum
        answer = answer & 0xffff
        answer = answer >> 8 | (answer << 8 & 0xff00)
        return answer

    def create_packet(self, addr, id, seq = 1):
        # Creates an ICMP packet, including header.  See RFC 792 for details.
        #
        #  HEADER
        #    8-bits:    type
        #    8-bits:    code
        #    16-bits:   checksum
        #    16-bits:   id
        #    16-bits:   sequence   
        #  DATA
        #    variable: data
        #
        # 'type' value for ICMP_ECHO_REQUEST is 8.
        # 'code' value should be 0.
        # 'checksum' is a 16-bit one's complement checksum of the entire packet
        #
        #  NOTE: since the checksum includes it's own value, calculate checksum as
        #    if it were set to zero. 
        header = struct.pack('bbHHh', 8, 0, 0, id, seq)
        #data = struct.pack('d', time.time())
        data = struct.pack('d', time.time()) + PAYLOAD
        fake_packet = header + data
        new_checksum = struct.pack('H', socket.htons(self.checksum(fake_packet)))
        packet = fake_packet[:2] + new_checksum + fake_packet[4:]
        return packet
        
    def ping(self, addr, id=1, seq=1, verbose = False):
        self.sent += 1
        addr = socket.gethostbyname(addr)
        packet = self.create_packet(addr, id, seq)
        if verbose:
            print "Pinging %s (id=%s seq=%s)" % (addr, id, seq)
        # Python requires a tuple of (addr, port), but the system call actually doesn't
        #   require a port.  So we'll send '1' as a dummy port value.
        self.sock.sendto(packet, (addr, 1))

if __name__ == "__main__":

    host_list = ['justin.tv', 'google.com']
    ping_count = 5000
    total_pings = len(host_list) * ping_count
    pinger = Pinger()
    for host in host_list:
        pinger.register(host, 1)
    for i in range(ping_count):
        for host in host_list:
            pinger.ping(host, 1, i+1)
            pinger.poll()
    while True:
        pinger.poll()
        if pinger.received >= total_pings:
            print "done"
            break

