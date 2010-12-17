import matplotlib.pyplot as plt
import pickle

hostinfo = pickle.load(open('hosts.dat', 'r'))
x = [host['loss'] for host in hostinfo if host['loss'] and host['loss'] != 100.0]
print "Data points: %s" % len(x)

mu, sigma = 100, 15
n, bins, patches = plt.hist(x, 100, range=(0, 100), facecolor='green', alpha=0.75)

plt.xlabel('Packet Loss (%)')
plt.ylabel('Number of networks (out of 18505)')
plt.grid(True)

plt.show()