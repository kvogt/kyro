from twisted.python import log
from twisted.internet import reactor, protocol
import sys, traceback, struct, math
from kyro.util import *

__author__    = "Kyle Vogt <kyle@justin.tv>"
__version__   = "0.1"
__copyright__ = "Copyright (c) 2010, Kyle Vogt"
__license__   = "MIT"        

# Implements BGP4 wire protocol as a twisted.internet.protocol.Protocol
# See http://www.ietf.org/rfc/rfc1771.txt)
#
# To use this:
#     create a new class that inherits bgp.Protocol
#     implement messageReceived()
#     create a twisted server factory and set your new class as the protocol
#
# See router.py for kyro's usage of this class to implement a BGP peer router

# Serialization functions
def header(kind, data):
    length = len(data) + 19
    return (chr(0xFF) * 16) + struct.pack('!H', length) + chr(kind) + data

def openMessage(params):
    data = ''
    data += chr(params['version'])
    data += unshort(params['sender_as'])
    data += unshort(params['hold_time'])
    data += unip(params['bgp_identifier'])
    data += chr(params.get('optional_length', 0))
    data += str(params.get('optional_data', ''))
    return header(1, data)

def updateMessage(params):
    data = ''
    data += unshort(params['withdrawn_routes_length'])
    data += params['withdrawn_routes']
    if not isinstance(params['path_attributes'], str):
        encodePathAttributes(params['path_attributes'])
    data += unshort(len(params['path_attributes']))
    data += params['path_attributes']
    data += params['network_layer_reachability_information']
    return header(2, data)

def keepAliveMessage(params = {}):
    return header(4, '')

def encodePathAttributes(params):
    data = ''
    for param in params:
        flags = param['flags']
        type_code = param['type_code']
        attribute = param['value']
        data += chr(flags)
        if type_code == 'ORIGIN': 
            type_code = 1
            if attribute == 'IGP' : attribute = 0
            if attribute == 'EGP' : attribute = 1
            if attribute == 'INCOMPLETE' : attribute = 2
        elif type_code == 'AS_PATH': 
            type_code = 2
            a_data = ''
            for segment in attribute:
                segment_type, segment_length, asns = segment
                if segment_type == "AS_SET":
                    segment_type = 1
                elif segment_type == "AS_SEQUENCE":
                    segment_type = 2
                a_data += chr(segment_type)
                a_data += chr(segment_length)
                a_data += ''.join([unshort(asn) for asn in asns])    
            attribute = a_data            
        elif type_code == 'NEXT_HOP':
            type_code = 3
            attribute = unip(attribute)
        elif type_code == 'MULTI_EXIT_DISC': 
            type_code = 4
            attribute = unlong(attribute)
        elif type_code == 'LOCAL_PREF': 
            type_code = 5
            attribute = unlong(attribute)
        elif type_code == 'ATOMIC_AGGREGATE': 
            type_code = 6
        elif type_code == 'AGGREGATOR': 
            type_code = 7
            attribute = unshort(attribute[0]) + unip(attribute[1])
        elif type_code == 'COMMUNITIES': 
            type_code = 8     
            attribute = ''.join([''.join(unshort(part) for part in com.split(':')) for com in attribute])
        data += chr(type_code)
        data += attribute
    return data

# Parser
class Protocol(protocol.Protocol):
    def __init__(self, config={}):
        self.state = 'start'
        self.buffer = ''
        self.message = {}
        self.total_routes = 0
        self.current_routes = 0
        self.bytes_received = 0
        self.config = config
        
    def connectionMade(self):
        self.connected = True
        self.ip = self.transport.getPeer().host
        self.config = self.factory.config
        log.msg('Got a connection from %s' % self.ip)
        log.msg('SENDING OPEN')
        params = {
            'version' : 4,
            'sender_as' : int(self.config['sender-as']),
            'hold_time' : int(self.config['hold-time']),
            'bgp_identifier' : self.config['bgp-identifier'],
            'optional_length' : 0,
            'optional_data' : '',
        }
        self.transport.write(openMessage(params))
        
    def connectionLost(self, reason):
        log.msg('Lost connection to %s.' % self.ip)
        self.connected = False
                
    def keepAlive(self):
        if self.connected:
            log.msg('SENDING KEEPALIVE')
            self.transport.write(keepAliveMessage())
            self.keepAliveDeferred = reactor.callLater(int(self.config['hold-time']) / 3.0, self.keepAlive)

    def advance(self, bytes, fun, next):
        if len(self.buffer) >= bytes:
            self.message[self.state] = fun(self.buffer[:bytes])
            self.state = next
            if len(self.buffer) > bytes:
                self.buffer = self.buffer[bytes:]
            else:
                self.buffer = ''

    def dataReceived(self, data):
        self.bytes_received += len(data)
        self.buffer += data

        #log.msg('Recieved %s bytes, buffer is %s bytes (%s all time)' % (len(data), len(self.buffer), self.bytes_received))
        
        # Header
        if self.state == 'start':
            self.advance(16, str, 'length')
        if self.state == 'length':
            self.advance(2, short, 'type')
        if self.state == 'type':
            self.advance(1, ord, 'dispatch')
        if self.state == 'dispatch':
            kind = self.message['type']
            if kind == 1: 
                self.message['type'] = 'OPEN'
                self.state = 'version'
            elif kind == 2: 
                self.message['type'] = 'UPDATE'
                self.state = 'withdrawn_routes_length'
            elif kind == 3: 
                self.message['type'] = 'NOTIFICATION'
                self.state = 'error_code'
            elif kind == 4: 
                self.message['type'] = 'KEEPALIVE'
                self.state = 'start'
            else: self.state = 'start'

        # OPEN
        if self.state == 'version':
            self.advance(1, ord, 'sender_as')
        if self.state == 'sender_as':
            self.advance(2, short, 'hold_time')
        if self.state == 'hold_time':
            self.advance(2, short, 'bgp_identifier')
        if self.state == 'bgp_identifier':
            self.advance(4, ip, 'optional_length')
        if self.state == 'optional_length':
            self.advance(1, ord, 'optional_data')
        if self.state == 'optional_data':
            self.advance(self.message['optional_length'], str, 'start')
            
        # UPDATE
        if self.state == 'withdrawn_routes_length':
            self.advance(2, short, 'withdrawn_routes')
        if self.state == 'withdrawn_routes':
            length = self.message['withdrawn_routes_length']
            self.advance(length, str, 'total_path_attributes_length')
        if self.state == 'total_path_attributes_length':
            if not isinstance(self.message['withdrawn_routes'], list):
                self.parseWithdrawnRoutes()
            self.advance(2, short, 'path_attributes')
        if self.state == 'path_attributes':
            length = self.message['total_path_attributes_length']
            self.advance(length, str, 'network_layer_reachability_information')
        if self.state == 'network_layer_reachability_information':
            if not isinstance(self.message['path_attributes'], list):
                self.parsePathAttributes()
            length = max(self.message['length'] - 23 - self.message['total_path_attributes_length'] - self.message['withdrawn_routes_length'], 0)
            self.advance(length, str, 'start')
            if self.state == 'start':
                self.parseNetworkLayerReachabilityInformation()
            
        # NOTIFICATION
        if self.state == 'error_code':
            self.advance(1, ord, 'error_subcode')
        if self.state == 'error_subcode':
            self.advance(1, ord, 'data')
        if self.state == 'data':
            length = self.message['length'] - 21
            self.advance(length, str, 'start')        
            
        if self.message and self.state == 'start':
            del self.message['start']
            if self.message.get('type', '') == 'OPEN':
                self.openMessageReceived(self.message)
            else:
                self.messageReceived(self.message)
            self.message = {}
        
            # Continue processing messages
            if len(self.buffer): self.dataReceived('')
            
    def parsePrefixes(self, data):
        prefixes = []
        offset = 0
        while offset < len(data):
            length = ord(data[offset])
            offset += 1
            if length:
                bytes = int(math.ceil(float(length) / 8.0))
                prefix = long(data[offset : offset + bytes])
                offset += bytes
                prefix = prefix >> (bytes * 8 - length)
                prefix = prefix << (32 - length)
                prefixes.append('%s/%s' % (ip(prefix), length))
            else:
                prefixes.append('0.0.0.0/0')
        return prefixes

    def parseWithdrawnRoutes(self):
        data = self.message['withdrawn_routes']
        self.message['withdrawn_routes'] = self.parsePrefixes(data)
        
    def parsePathAttributes(self):
        offset = 0
        attributes = []
        while offset < self.message['total_path_attributes_length']:
            # Read attribute data
            flags = ord(self.message['path_attributes'][offset])
            offset += 1
            type_code = ord(self.message['path_attributes'][offset])
            offset += 1
            if flags & (2 ** 5):
                length = short(self.message['path_attributes'][offset:offset + 2])
                offset += 2
            else:
                length = ord(self.message['path_attributes'][offset:offset + 1])
                offset += 1
            if length:
                attribute = pick(length)(self.message['path_attributes'][offset:offset + length])
                offset += length
            else:
                attribute = None
            # Parse attribute
            if type_code == 1:
                type_code = "ORIGIN"
                if attribute == 0:
                    attribute = "IGP"
                elif attribute == 1:
                    attribute = "EGP"
                elif attribute == 2:
                    attribute = "INCOMPLETE"
            elif type_code == 2:
                type_code = "AS_PATH"
                a_offset = 0
                segments = []
                if attribute:
                    while a_offset < len(attribute):
                        segment_type = ord(attribute[a_offset])
                        if segment_type == 1:
                            segment_type = "AS_SET"
                        elif segment_type == 2:
                            segment_type = "AS_SEQUENCE"
                        a_offset += 1
                        segment_length = ord(attribute[a_offset])
                        a_offset += 1
                        asns = []
                        for i in xrange(segment_length):
                            asns.append(short(attribute[a_offset : a_offset + 2]))
                            a_offset += 2
                        segments.append((segment_type, segment_length, asns))
                attribute = segments
            elif type_code == 3:
                type_code = "NEXT_HOP"
                attribute = ip(attribute)
            elif type_code == 4:
                type_code = "MULTI_EXIT_DISC"
                attribute = long(attribute)
            elif type_code == 5:
                type_code = "LOCAL_PREF"
                attribute = long(attribute)
            elif type_code == 6:
                type_code = "ATOMIC_AGGREGATE"
            elif type_code == 7:
                type_code = "AGGREGATOR"
                attribute = (short(attribute[0:2]), ip(attribute[2:6]))
            elif type_code == 8:
                type_code = "COMMUNITIES"
                a_offset = 0
                communities = []
                while a_offset < len(attribute):
                    communities.append({
                        'asn' : short(attribute[a_offset : a_offset + 2]),
                        'value' : short(attribute[a_offset + 2 : a_offset + 4])
                    })
                    a_offset += 4
                attribute = communities
            elif type_code == 9:
                type_code = "ORIGINATOR_ID"
                attribute = ip(attribute)
            elif type_code == 10:
                type_code = "CLUSTER_LIST"
                a_offset = 0
                clusters = []
                while a_offset < len(attribute):
                    clusters.append(ip(attribute[a_offset : a_offset + 4]))
                    a_offset += 4
                attribute = clusters
            else:
                log.msg('unknown path attribute type_code: %s' % type_code)
            attributes.append({
                'flags' : flags, 
                'type_code' : type_code,
                'value' : attribute
            })
        self.message['path_attributes'] = attributes

    def extractCommunity(self, message, asn):
        coms = []
        for attribute in message.get('path_attributes', []):
            if attribute['type_code'] == 'COMMUNITIES':
                coms = attribute['value']
        for com in coms:
            if int(asn) == int(com['asn']):
                return int(com['value'])
        return 0
    
    def extractLocalPreference(self, message):
        for attribute in message.get('path_attributes', []):
            if attribute['type_code'] == 'LOCAL_PREF':
                return int(attribute['value'])
        return None
    
    def parseNetworkLayerReachabilityInformation(self):
        data = self.message['network_layer_reachability_information']
        routes = self.parsePrefixes(data)
        self.message['network_layer_reachability_information'] = routes
        
    def openMessageReceived(self, message):
        # Start keepalive loop (send every hold-time / 3 seconds)
        self.peer = message  
        self.keepAlive()
            
    def messageReceived(self, message):
        # OVERRIDE ME!
        log.msg(message)
