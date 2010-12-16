# Route database
class RouteDB:
    def __init__(self, config):
        self.config = config
        try:
            self.pool = self.connect()
        except:
            log.msg('ERROR: Can\'t connect to db!')
            traceback.print_exc()
            sys.exit(0)

    def connect(self):
        dbsettings = {
            'database': self.config['db-name'],
            'host': self.config['db-host'],
            'port': self.config['db-port'],
            'user': self.config['db-user'],
            'password': self.config['db-pass'],
        }
        dbpool = adbapi.ConnectionPool("pyPgSQL.PgSQL", **dbsettings)
        return dbpool
        
    def flush(self, peer):
        "Flush all routes for a given peer"
        try:
            q = "delete from routes where bgp_id = '%s' and router_id = '%s'" % (self.config['bgp-identifier'], peer['bgp_identifier'])
            log.msg('FLUSH: Flushing routes for bgp_id %s and router_id %s' % (self.config['bgp-identifier'], peer['bgp_identifier']))
            if self.config['verbose']: log.msg(q)
            return self.pool.runOperation(q)
        except:
            log.msg('FLUSH: Error!')
            log.msg(traceback.format_exc())
            return False

    def update(self, new_routes, community, pref, router_id):
        "Insert or update data for the supplied route table"
        def _(txn, _cluster_name, _pref, _new_routes, _bgp_identifier, _router_id):
            if not _pref: _pref = 75
            q = "select id from clusters where name='%s'" % _cluster_name
            txn.execute(q)
            try:
                cluster_id = txn.fetchall()[0][0]
            except:
                log.msg('Could not get cluster id for name %s, pref %s, routes %s, router_id %s:\n%s' % (
                    _cluster_name, _pref, repr(_new_routes), _router_id, traceback.format_exc()))
                return False
            q = "select id, prefix from routes where prefix in ('" + "', '".join(_new_routes.keys()) + "') and bgp_id = '%s' and router_id = '%s' and cluster_id = '%s'" % (_bgp_identifier, _router_id, cluster_id)
            if self.config['verbose']: log.msg(q)
            txn.execute(q)
            try:
                current_routes = txn.fetchall()
            except:
                log.msg('Error getting data on existing routes: %s' % traceback.format_exc())
            updated = []
            for current_route in current_routes:
                prefix = current_route[1]
                new_route = _new_routes[prefix]
                q = """
                    update routes set asn = %s, preference = %s, bgp_id = '%s', router_id = '%s', cluster_id = '%s' where id = %s;""" % (
                    new_route[1][-1], _pref, _bgp_identifier, _router_id, cluster_id, current_route[0])
                if self.config['verbose']: log.msg(q)
                txn.execute(q)
                updated.append(prefix)                
            #log.msg('new routes:\n%s' % repr(new_routes))
            for prefix, route in [(p, list(r)) for (p, r) in new_routes.items() if p not in updated]:
                #log.msg('prefix: %s route: %s' % (prefix, route))
                # warn on routes with no AS-PATH (probably local routes that shouldn't be there!)
                if not len(route[1]):
                    log.msg('WARN: Received route with no AS-PATH (using sender-as of %s): prefix: %s route: %s' % (self.config['sender-as'], prefix, repr(route)))
                    route[1] = [int(self.config['sender-as'])]
                #    continue
                # THIS WILL INSERT DST_AS
                #q = """
                #    insert into routes (cluster_id, prefix, asn, preference, bgp_id, router_id)
                #    values ('%d', '%s', '%s', '%s', '%s', '%s')""" % (
                #    cluster_id, prefix, route[1][-1], _pref, _bgp_identifier, _router_id)

                # THIS WILL INSERT ORIGIN_AS (peer AS)
                q = """
                    insert into routes (cluster_id, prefix, asn, preference, bgp_id, router_id)
                    values ('%d', '%s', '%s', '%s', '%s', '%s')""" % (
                    cluster_id, prefix, route[1][0], _pref, _bgp_identifier, _router_id)
                if self.config['verbose']: log.msg(q)
                try:
                    if self.config['verbose']: log.msg(q)
                    txn.execute(q)
                except:
                    log.msg('ERROR: Could not insert route using query %s\n%s' % (q, traceback.format_exc()))
        # convert community to cluster tag
        cluster_name = self.config['community-mapping'].get(str(community))
        if not cluster_name:
            log.msg('No cluster name found for community %s, using default cluster name of %s' % (community, self.config['db-cluster-name']))
            cluster_name = self.config['db-cluster-name']
        #log.msg('updating route db with cluster name %s' % cluster_name)
        return self.pool.runInteraction(_, cluster_name, pref, new_routes, self.config['bgp-identifier'], router_id)

    def withdraw(self, old_prefixes, router_id):
        "Delete a list of prefixes"
        for old_prefix in old_prefixes:
            q = "delete from routes where prefix = '%s' and bgp_id = '%s' and router_id = '%s'" % (
                old_prefix, self.config['bgp-identifier'], router_id)
            if self.config['verbose']: log.msg(q)
            self.pool.runOperation(q)
        return True