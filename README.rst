=======
 Kyro
=======

Introduction
------------

Kyro is a set of python daemons designed to measure realtime network
performance and inject optimal routes into a BGP router.

Features at a Glance
--------------------

* Uses 'ping' command to measure latency and packet loss
* Implements BGP4 protocol and can peer with BGP routers
* Written in Python using the Twisted event framework 

Architecture
------------

There are two daemons: router.py and analyzer.py

Router.py uses Kyro's BGP library to listen for route updates from a BGP speaking router.  These route updates are used to populate a list of prefixes that should be optimized.

Analyzer.py continuously checks the packet loss and mean round trip time for each prefix over each path.  If a more optimal path is found than the current best path, analyzer.py will ask router.py to inject the new route into
the BGP router's routing table.

Dependencies
------------

* Twisted - http://twistedmatrix.com/trac/wiki/Downloads
* matplotlib - http://matplotlib.sourceforge.net/

Detailed Overview
-----------------

Run router.py --help for more information.
