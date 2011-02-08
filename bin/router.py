#!/usr/bin/env python
from twisted.python import log, usage
from twisted.internet import reactor, protocol
from kyro import bgp, rib
import sys

# Logic for the BGP router
class Peer(bgp.Protocol):
    
    def __init__(self):
        bgp.Protocol.__init__(self)
        self.rib = {}
        self.logTableStats()
    
    def logTableStats(self):
        if self.factory.config.get('statistics'):
            log.msg('STATS (%s-%s): adj_rib: %s routes\ttotal: %s routes' % (self.peer['bgp_identifier'], self.peer['sender_as'], len(self.rib), self.total_routes))
            reactor.callLater(5.0, self.logTableStats)

    def messageReceived(self, message):
        # Called whenever a BGP message arrives from a peer
        log.msg(message)
        if message['type'] != 'UPDATE': return
        if message['network_layer_reachability_information']:
            prefixes = message['network_layer_reachability_information']
            for prefix in prefixes:
                self.total_routes += 1
                self.rib[prefix] = message
        if message['withdrawn_routes']:
            prefixes = message['withdrawn_routes']
            for prefix in prefixes:
                if prefix in self.rib:
                    del self.rib[prefix]
                
class PeerFactory(protocol.ServerFactory):
    def __init__(self, config):
        log.msg('config: %s' % repr(config))
        self.config = config
        self.protocol = Peer

if __name__ == '__main__':

    class Options(usage.Options):
        optFlags = [
            ['verbose', 'v', 'Verbose logging'],
            ['statistics', 's', 'Enable BGP statistics logging'],            
        ]
        optParameters = [
            ['log', 'l', 'stdout', 'Log file'],
            ['sender-as', 'a', '64496', 'Autonomous System Number (ASN)'],
            ['injection-community', 'c', '1337', 'Community for tagging outgoing routes'],            
            ['bgp-identifier', 'i', '127.0.0.1', 'BGP identifier'],
            ['hold-time', 'o', '180', 'BGP hold time'],
            ['bgp-port', 'b', '179', 'Local BGP server port'],
        ]
    config = {}
    try:
        options = Options()
        options.parseOptions()
        config = dict(options)
    except usage.UsageError, errortext:
        print '%s: %s' % (sys.argv[0], errortext)
        print '%s: Try --help for usage details.' % (sys.argv[0])
        sys.stdout.flush()
        sys.exit(1)

    if config['log'] == 'stdout':
        l = sys.stdout
    else:
        l = open(config['log'], 'a')

    log.startLogging(l)
    from twisted.internet import reactor  

    # Router server-side
    reactor.listenTCP(int(config['bgp-port']), PeerFactory(config))

    # Run
    reactor.run()