#!/usr/bin/env python
from twisted.python import log
from twisted.internet import reactor, utils
import os
import random
import time
import pickle

is_linux = 'Linux' in os.uname()[0]

class Pinger:
    
    def __init__(self):
        self.pool = []
        self.pool_size = 30
        self.ping_command = os.popen("which ping").read().strip()
        self.queue = []
        self.prefixes = []
        self.running = True
        self.interval = 90
        self.completed = 0
        self.hosts = []
        self.poll()
        self.stats()
        
    def addHost(self, host):
        hostinfo = {
            'host' : host,
            'last_ping' : time.time(),
            'latency' : None,
            'loss' : None,
            'interval' : self.interval
        }
        self.hosts.append(hostinfo)
        if self.running:
            self.ping(hostinfo)

    def pingCompleted(self, result, hostinfo):
        self.completed += 1
        self.pool.remove(hostinfo['host'])
        self.queuePing(hostinfo)
        loss = 0.0
        avg = 0.0
        for line in result.split('\n'):
            if is_linux:
                if 'rtt' in line:
                    times = line.split()[line.replace(',', '').split().index('ms') - 1]
                    avg = float(times.split('/')[1])
                    hostinfo['latency'] = avg
                if 'loss' in line:
                    loss = float(line.split()[-5].replace('%', ''))
                    hostinfo['loss'] = loss
            else:
                if 'round-trip' in line:
                    times = line.split()[-2]
                    avg = float(times.split('/')[1])
                    hostinfo['latency'] = avg
                if 'loss' in line:
                    print line
                    loss = float(line.split()[-3].replace('%', ''))
                    if loss != 100.0: 
                        hostinfo['loss'] = loss
        print "ping_complete(%s): %s ms, %.2f%% packet loss" % (hostinfo['host'], avg, loss)
    
    def pingFailed(self, reason):
        print "Ping Failed:"
        print reason
    
    def queuePing(self, hostinfo):
        next_ping = hostinfo['last_ping'] + hostinfo['interval']
        now = time.time()
        if next_ping < now:
            if len(self.queue) == 0:
                self.ping(hostinfo)
            else:
                self.queue.append(hostinfo)
        else:
            reactor.callLater(next_ping - now, self.ping, hostinfo)        
        
    def ping(self, hostinfo):
        hostinfo['last_ping'] = time.time()
        if len(self.pool) < self.pool_size:
            print "ping_start(%s)" % hostinfo['host']
            uid = hostinfo['host'] + "_%08s_" % random.randint(0, 99999999)
            if is_linux:
                args = "-i .1 -c 300 %s" % hostinfo['host']
            else:
                args = "-i 1 -c 100 %s" % hostinfo['host']
            output = utils.getProcessOutput(self.ping_command, args.split())
            output.addCallbacks(self.pingCompleted, self.pingFailed, [hostinfo])
            self.pool.append(hostinfo['host'])
        else:
            print "ping_queue(%s)" % hostinfo['host']
            self.queue.append(hostinfo)

    def poll(self):
        available = self.pool_size - len(self.pool)
        if available > 0:
            for i in range(available):
                if len(self.queue):
                    self.ping(self.queue.pop(0))
        reactor.callLater(1.0, self.poll)
        
    def stats(self):
        measured = len([h for h in self.hosts if h['latency']])
        hosts = 1 if not len(self.hosts) else len(self.hosts)
        print "stats:"
        print "\tqueue: %s" % len(self.queue)
        print "\trunning: %s" % len(self.pool)
        print "\tpings: %s" % self.completed
        print "\tuniques: %s" % measured
        print "\ttotal hosts: %s" % len(self.hosts)
        print "\tmeasured: %.2f%%" % (float(measured) / float(hosts) * 100.0)
        reactor.callLater(10.0, self.stats)
        
if __name__ == "__main__":
    
    prefixes = ['64.91.18.0', '182.54.192.0', '202.83.96.0', '165.233.200.0', '138.242.96.0', '20.139.8.0']
    # Or, for something more useful, create a list of ip prefixes, one per line, 
    # and save them in ips.txt.  It should look something like this:
    #     
    # 64.91.18.0/24
    # 182.54.192.0/24
    # 202.83.96.0/24
    #
    # (etc)
    #
    #prefixes = [p.split('/')[0] for p in open('ips.txt', 'r').readlines() if p]
    
    random.shuffle(prefixes)
    pinger = Pinger()
    for prefix in prefixes:
        host = prefix.replace('.0', '.1')
        pinger.addHost(host)
    reactor.run()
    print "Terminated, dumping data to hosts.dat..."
    pickle.dump(pinger.hosts, open('hosts.dat', 'w'))
    print "Finshed.  Raw data:"
    # To prevent weird terminal error
    time.sleep(5.0)
    print pinger.hosts
    
