# RIB
class RIB:

    def __init__(self, peer):
        self.table = {}
        self.peer = peer

    def update(self, prefix, next_hop, as_path):
        log.msg('UPDATE (%s-%s): %s %s %s' % (self.peer['bgp_identifier'], self.peer['sender_as'], prefix, next_hop, as_path))
        self.table[prefix] = (next_hop, as_path)

    def withdraw(self, prefix):
        try:
            log.msg('WITHDRAW (%s-%s): %s' % (self.peer['bgp_identifier'], self.peer['sender_as'], prefix))
            del self.table[prefix]
        except:
            log.msg('WARN: %s cannot be removed (not in RIB)' % prefix)

    def num_routes(self):
        return len(self.table)
