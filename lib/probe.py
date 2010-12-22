#!/usr/bin/env python
import socket
import select
import time
import struct
import sys
import os
import util

PAYLOAD = 'x' * 184

class Probe():
    
    def __init__(self, host):
        self.host = host
        self.ip = socket.gethostbyname(host)
        self.next_ts = None
        self.ping_ts = None
        self.interval = 5.0
        self.count = 60
        self.current_ttl = 0
        self.max_ttl = 0
        self.mapping_tries = 0
        self.max_mapping_tries = 5
        self.seq = 0
        self.timeout = 2.0
        self.mapped = False
        self.waiting = False
        self.mapped_ip = self.ip
        
    def log(self, msg):
        print "Probe(%s) %s" % (self.host, msg)

class Prober():
    
    def __init__(self):
        self.pid = os.getpid()
        self.probes = []
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
        self.sock.setblocking(False)
        # Need massive socket receive buffer if concurrency is high
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1048576 * 2)
        
    def add(self, host):
        if host not in [probe.host for probe in self.probes]:
            self.probes.append(Probe(host))
        
    def get_probe(self, ip):
        probe = [p for p in self.probes if p.ip == ip]
        if probe:
            return probe[0]
        else:
            return None
            
    def run(self):
        # Advance state of probes that are ready
        for probe in self.probes:
            now = time.time()
            if not probe.next_ts <= now: continue
            if probe.waiting:
                # Last ping timed out, so back off a TTL
                if probe.mapping_tries == probe.max_mapping_tries: 
                    probe.mapped = True
                    probe.max_ttl -= 1
                    probe.log("MAPPED mapped_ip=%s max_ttl=%s" % (probe.mapped_ip, probe.max_ttl))
                else:
                    probe.log("MAPPING_TIMEOUT")
                    probe.mapping_tries += 1
            elif not probe.mapped:
                # If probe isn't mapped, advance TTL and send a ping
                probe.max_ttl += 1
            probe.waiting = True
            # Schedule a timeout handler
            probe.next_ts = now + probe.timeout
            probe.ping_ts = now
            probe.seq += 1
            # Send the ping!
            probe.log("PING ip=%s id=%s seq=%s ttl=%s" % (probe.ip, self.pid, probe.seq, probe.max_ttl))
            self.ping(probe.ip, id=self.pid, seq=probe.seq, ttl=probe.max_ttl)
        # Process incoming data
        while True:
            now = time.time()
            rlist, wlist, xlist = select.select([self.sock, sys.stdin], [], [], 0.01)
            if not rlist:
                break
            if sys.stdin in rlist:
                line = sys.stdin.readline()
                if self.state == STATE_COMMAND:
                    line = line.strip().upper()
                    if line.startswith == 'PING':
                        # TODO: allow registration of pings' remotely
                        pass
            if self.sock in rlist:
                # Should never need more than ~50 bytes
                data, paddr = self.sock.recvfrom(256)
                paddr = paddr[0]
                icmpHeader = data[20:24]
                ptype, pcode, checksum = struct.unpack(
                    "bbH", icmpHeader
                )
                if ptype == 0:
                    # ICMP Echo Reply
                    body = data[24:40]
                    pid, pseq, tstamp = struct.unpack(
                        "HhL", body
                    )
                    probe = self.get_probe(paddr)
                    if probe:
                        tstamp = data[28:36]
                        et = int(time.time() * 1000.0)
                        [st] = struct.unpack("L", tstamp)
                        ms = (et - st)
                        if not probe.mapped:
                            probe.mapped = True
                            probe.log("MAPPED mapped_ip=%s max_ttl=%s" % (probe.mapped_ip, probe.max_ttl))
                        probe.log("PONG type=echo_reply id=%s seq=%s ms=%s" % (pid, pseq, ms))
                        probe.next_ts = now + probe.interval
                        probe.waiting = False
                elif ptype == 11 and pcode == 0:
                    # ICMP Time Exceeded
                    original_ip_header, original_data = data[28:48], data[48:56]
                    dest_addr = util.ip(original_ip_header[16:20])
                    probe = self.get_probe(dest_addr)
                    if not probe: return
                    # Original datagram is included after the IP header
                    otype, ocode, ochecksum, oid, oseq = struct.unpack(
                        "bbHHh", original_data
                    )
                    ms = int((now - probe.ping_ts) * 1000.0)
                    probe.log("PONG type=time_exceeded id=%s seq=%s addr=%s ms=%s" % (oid, oseq, paddr, ms))
                    if probe.mapped:
                        # Just schedule the next regular ping
                        probe.next_ts = now + probe.interval
                        probe.waiting = False
                    if not probe.mapped:
                        # Set new max_ttl, if necessary, and continue mapping
                        probe.max_ttl = max(oseq, probe.max_ttl)
                        probe.next_ts = now
                        probe.waiting = False
                        probe.mapped_ip = paddr
                        # In case this was a retry, reset the counter
                        probe.mapping_tries = 0
        
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
        data = struct.pack('L', int(time.time() * 1000.0)) + PAYLOAD
        fake_packet = header + data
        new_checksum = struct.pack('H', socket.htons(self.checksum(fake_packet)))
        packet = fake_packet[:2] + new_checksum + fake_packet[4:]
        return packet
        
    def ping(self, addr, id=1, seq=1, ttl=255, verbose = False):
        addr = socket.gethostbyname(addr)
        packet = self.create_packet(addr, id, seq)
        if verbose:
            print "Pinging %s (id=%s seq=%s ttl=%s)" % (addr, id, seq, ttl)
        self.sock.setsockopt(socket.SOL_IP, socket.IP_TTL, ttl)
        # Python requires a tuple of (addr, port), but the system call actually doesn't
        #   require a port.  So we'll send '1' as a dummy port value.
        self.sock.sendto(packet, (addr, 1))

if __name__ == "__main__":
    hosts = ['cnn.com'] #, 'google.com', 'justin.tv', 'yahoo.com', 'nytimes.com', 'ustream.tv', 'ycombinator.com',
        #'blogtv.com', 'comcast.com', 'ea.com']
    probe = Prober()
    for host in hosts:
        print "Adding probe for %s..." % host
        probe.add(host)
    while True:
        probe.run()
            
            

