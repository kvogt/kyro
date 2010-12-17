#!/usr/bin/env python
from twisted.python import log, usage
from twisted.internet import reactor, protocol
from kyro import bgp
import sys

# Logic for the BGP router
class Peer(bgp.Protocol):
    
    def logTableStats(self):
        log.msg('STATS (%s-%s): adj_rib: %s routes\ttotal: %s routes' % (self.peer['bgp_identifier'], self.peer['sender_as'], self.adj_rib.num_routes(), self.total_routes))
        reactor.callLater(5.0, self.logTableStats)

    def openMessageReceived(self, message):
        bgp.Protocol.openMessageReceived(self, message)
        # Set up our own Routing Information Base for this peer
        self.adj_rib = RIB(self.peer)
        if self.factory.config['statistics']:
            self.logTableStats()
            
    def messageReceived(self, message):
        log.msg(message)
        if message['type'] == 'UPDATE':
            attrs = message.get('path_attributes', [])
            as_path = ''
            next_hop = ''
            for attr in attrs:
                if attr.get('type_code', '') == 'AS_PATH':
                    try:
                        as_path = attr['value'][0][2]
                        origin_as = attr['value'][0][2][0]
                        dest_as = attr['value'][0][2][-1]
                        log.msg('Learned route to %s via %s' % (dest_as, origin_as))
                    except:
                        pass
                        #log.msg('Learned local route')
                if len(attr) > 2 and attr['type_code'] == 'NEXT_HOP':
                    next_hop = attr['value']
            if message['network_layer_reachability_information']:
                #log.msg('Added prefixes:')
                prefixes = message['network_layer_reachability_information']
                for prefix in prefixes:
                    #log.msg('\t%s' % route)
                    self.total_routes += 1
                    self.current_routes += 1
                    self.adj_rib.update(prefix, next_hop, as_path)
                new_routes = dict(zip(prefixes, [(next_hop, as_path) for i in range(len(prefixes))]))
                community = self.extractCommunity(message, self.config['sender-as'])
                pref = self.extractLocalPreference(message)
                #self.route_db.update(new_routes, community, pref, self.peer['bgp_identifier'])
            if message['withdrawn_routes']:
                #log.msg('Removed prefixs:')
                prefixes = message['withdrawn_routes']
                for prefix in prefixes:
                    #log.msg('\t%s' % route)
                    self.current_routes -= 1
                    self.adj_rib.withdraw(prefix)
            #self.route_db.withdraw(prefixes, self.peer['bgp_identifier'])
    
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