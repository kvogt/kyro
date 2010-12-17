import matplotlib.pyplot as plt
import pickle

hostinfo = pickle.load(open('hosts.dat', 'r'))
x = [host['latency'] for host in hostinfo if host['latency']]
print "Data points: %s" % len(x)

mu, sigma = 100, 15
n, bins, patches = plt.hist(x, 200, normed=1, range=(0, 800), facecolor='green', alpha=0.75)

plt.xlabel('Network Latency (ms)')
plt.ylabel('Frequency')
plt.axis([0, 800, 0, 0.01])
plt.grid(True)

plt.show()