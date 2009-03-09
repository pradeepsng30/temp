import datetime
import itertools
from math import exp, log, sqrt

import rpy2.robjects as robjects

from counter import Counter

import sys

class CRPGibbsSampler(object):
	def __init__(self, data, gibbs_iterations=1, cluster_precision=0.25, mh_mean=Counter(default=1.0), mh_precision=1.0):
		"""
		data: for now, counters of score-for-context (HUGE cardinality)
		gibbs_iterations: should be a number >= 1, large enough to
		ensure the chain is converged given updated params
		"""
		self._gibbs_iterations = gibbs_iterations
		self._data = data
		self._max_x = max(v['x'] for v in data.itervalues())
		self._min_x = min(v['x'] for v in data.itervalues())
		self._max_y = max(v['y'] for v in data.itervalues())
		self._min_y = min(v['y'] for v in data.itervalues())

		self._concentration = 0.9

		# fixed variance
		self._cluster_tau = cluster_precision

		# hyper-params for the mean
		self._mh_tau = mh_precision
		self._mh_mean = mh_mean

		# These will be learned during sampling
		self._datum_to_cluster = dict()
		self._cluster_to_datum = dict()

		self._iteration_likelihoods = []
		self._cluster_count = []

	def _sample_datum(self, datum):
		raise Exception("Not implemented")

	def _add_datum(self, name, datum, cluster):
		self._datum_to_cluster[name] = cluster
		self._cluster_to_datum.setdefault(cluster, []).append(datum)

	def _remove_datum(self, name, datum):
		cluster = self._datum_to_cluster.get(name)
		if cluster == None: return

		cluster = self._cluster_to_datum[cluster].remove(datum)
		del self._datum_to_cluster[name]

	def gibbs(self, iterations=None):
		# use gibbs sampling to find a sufficiently good labelling
		# starting with the current parameters and iterate
		if not iterations:
			iterations = self._gibbs_iterations

		for iteration in xrange(iterations):
			if iteration % 1000 == 0:
				print "*** Iteration %d starting (%s) ***" % (iteration, datetime.datetime.now())

			if self._cluster_to_datum:
				self._iteration_likelihoods.append(self.log_likelihood())
				self._cluster_count.append(len([c for c, v in self._cluster_to_datum.iteritems() if v]))
				if iteration % 1000 == 0:
					print "    Clusters: %d" % self._cluster_count[-1]
					print "    Likelihood: %f" % self._iteration_likelihoods[-1]
					self.plot(iteration)
			for name, datum in self._data.iteritems():
				# resample cluster for this data, given all other data
				# as fixed

				# first, remove this point from it's current cluster
				self._remove_datum(name, datum)
				# then find a new cluster for it to live in
				cluster = 0
				cluster = self._sample_datum(datum)
				# and, finally, add it back in
				self._add_datum(name, datum, cluster)

		print "Finished Gibbs with likelihood: %f" % self.log_likelihood()

	def log_likelihood(self):
		raise Exception("NotImplemented")

	def plot(self, iteration):
		r = robjects.r
		r.png("likelihood-%d.png" % iteration)
		r.plot(robjects.IntVector(range(1, len(self._iteration_likelihoods) + 1)), robjects.FloatVector(self._iteration_likelihoods), xlab="iteration", ylab="likelihood")
		r['dev.off']()

		r = robjects.r
		r.png("cluster-count-%d.png" % iteration)
		r.plot(robjects.IntVector(range(1, len(self._cluster_count) + 1)), robjects.FloatVector(self._cluster_count), xlab="iteration", ylab="# clusters")
		r['dev.off']()

		r.png("test-%d.png" % iteration)
		r.plot([self._min_x - 1.0, self._max_x + 1.0],
			   [self._min_y - 1.0, self._max_y + 1.0],
			   xlab="x", ylab="y", col="white")

		colors = itertools.cycle(("red", "green", "blue", "black", "purple", "orange"))
		for (cluster, cdata), color in zip(self._cluster_to_datum.iteritems(), colors):
			points_x = robjects.FloatVector([point['x'] for point in cdata])
			points_y = robjects.FloatVector([point['y'] for point in cdata])

			if not len(cdata): continue
			
			print "Cluster (size %d): %s" % (len(cdata), sum(cdata) / len(cdata))
			print color
			r.points(points_x, points_y, col=color)

			cmean = sum(cdata) / len(cdata)
			r.points(cmean['x'], cmean['y'], pch=21, cex=4.0, col=color)

		r['dev.off']()