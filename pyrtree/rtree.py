## R-tree.
# see doc/ref/r-tree-clustering-split-algo.pdf
from __future__ import absolute_import

MAXCHILDREN=10
MAX_KMEANS=5
MAX_CLUSTER_ITERATIONS=100
LEAF = 1
EMPTY = 2
import math, random, sys
import time
import array
import heapq
import itertools

from .rect import Rect, union_all, NullRect

class RTree(object):
    def __init__(self):
        self.count = 0
        self.stats = { 
            "overflow_f" : 0,
            "avg_overflow_t_f" : 0.0,
            "longest_overflow" : 0.0,
            "longest_kmeans" : 0.0,
            "sum_kmeans_iter_f" : 0,
            "count_kmeans_iter_f" : 0,
            "avg_kmeans_iter_f" : 0.0
            }

        # This round: not using objects directly -- they
        #   take up too much memory, and efficiency goes down the toilet
        #   (obviously) if things start to page.
        #  Less obviously: using object graph directly leads to really long GC
        #   pause times, too.
        # Instead, it uses pools of arrays:
        self.count = 0
        self.leaf_count = 0
        self._skyline_compatible = True
        self.skyline_stats = {}
        self.rect_pool = array.array('d')
        self.node_pool = array.array('L')
        self.kind_pool = bytearray()
        self.leaf_pool = [] # leaf objects. 

        self.cursor = _NodeCursor.create(self, NullRect)

    def _ensure_pool(self, idx):
        if len(self.rect_pool) < (4*idx):
            self.rect_pool.extend([0,0,0,0] * idx)
            self.node_pool.extend([0,0] * idx)
            self.kind_pool.extend([EMPTY] * idx)

    def insert(self,o, orect):
        self.cursor.insert(o,orect)
        assert(self.cursor.index == 0)
        self._skyline_compatible = self._skyline_compatible and (
            orect.x == orect.xx and orect.y == orect.yy
            and all(math.isfinite(v) for v in orect.coords()))

    def skyline(self):
        """Return original records on the 2-D minimum skyline using BBS.

        Only finite point rectangles are supported. Equal coordinates retain
        every record. Query counters describe the most recent successful call;
        expanded_nodes includes the root of a nonempty tree.
        """
        if not self._skyline_compatible:
            raise ValueError("skyline() requires finite point rectangles")

        started = time.perf_counter()
        stats = dict(expanded_nodes=0, pushed_entries=0, popped_entries=0,
                     pruned_before_push=0, pruned_after_pop=0,
                     dominance_comparisons=0, max_heap_size=0,
                     skyline_records=0, first_result_seconds=None)
        heap = []
        sequence = itertools.count()
        coordinates = []
        records = []

        def dominated(x, y):
            for sx, sy in coordinates:
                stats["dominance_comparisons"] += 1
                if sx <= x and sy <= y and (sx < x or sy < y):
                    return True
            return False

        def enqueue(node):
            x, y = node.rect.x, node.rect.y
            if dominated(x, y):
                stats["pruned_before_push"] += 1
                return
            # Coordinate tie breakers preserve dominance order even if two
            # distinct floating-point sums round to the same value.
            priority = (x + y, x, y)
            heapq.heappush(heap, (priority, next(sequence), node.index))
            stats["pushed_entries"] += 1
            stats["max_heap_size"] = max(stats["max_heap_size"], len(heap))

        root = self.cursor.lift()
        if root.rect is not NullRect:
            stats["expanded_nodes"] += 1
            for child in root.children():
                enqueue(child)
        node = root.lift()
        while heap:
            _, _, index = heapq.heappop(heap)
            stats["popped_entries"] += 1
            node._become(index)
            x, y = node.rect.x, node.rect.y
            if dominated(x, y):
                stats["pruned_after_pop"] += 1
                continue
            if node.is_leaf():
                coordinates.append((x, y))
                records.append(node.leaf_obj())
                if stats["first_result_seconds"] is None:
                    stats["first_result_seconds"] = time.perf_counter() - started
            else:
                stats["expanded_nodes"] += 1
                for child in node.children():
                    enqueue(child)

        stats["skyline_records"] = len(records)
        stats["elapsed_seconds"] = time.perf_counter() - started
        self.skyline_stats = stats
        return records

    def query_rect(self, r):
        for x in self.cursor.query_rect(r): yield x
    def query_point(self, p):
        for x in self.cursor.query_point(p): yield x
    def walk(self,pred):
        return self.cursor.walk(pred)

class _NodeCursor(object):
    @classmethod
    def create(cls, rooto, rect):
        idx = rooto.count
        rooto.count += 1
        
        rooto._ensure_pool(idx + 1)
        #rooto.node_pool.extend([0,0])
        #rooto.rect_pool.extend([0,0,0,0])

        retv = _NodeCursor(rooto,idx,rect,0,0)

        retv._save_back()
        return retv

    @classmethod
    def create_with_children(cls, children, rooto):
        rect = union_all([c for c in children])
        assert(not rect.swapped_x)
        nc = _NodeCursor.create(rooto,rect)
        nc._set_children(children)
        assert(not nc.is_leaf())
        return nc

    @classmethod
    def create_leaf(cls, rooto, leaf_obj, leaf_rect):
        rect = Rect(leaf_rect.x,leaf_rect.y,leaf_rect.xx,leaf_rect.yy)
        res = _NodeCursor.create(rooto, rect)
        idx = res.index
        rooto.kind_pool[idx] = LEAF
        res.first_child = rooto.leaf_count
        rooto.leaf_count += 1
        res.next_sibling = 0
        rooto.leaf_pool.append(leaf_obj)
        res._save_back()
        res._become(idx)
        assert(res.is_leaf())
        return res

    __slots__ = ("root","npool","rpool","index","rect","next_sibling","first_child")

    def __init__(self, rooto, index, rect, first_child, next_sibling):
        self.root = rooto
        self.rpool = rooto.rect_pool
        self.npool = rooto.node_pool

        self.index = index
        self.rect = rect
        self.next_sibling = next_sibling
        self.first_child = first_child

    def walk(self, predicate):
        if self.rect is NullRect:
            return
        if (predicate(self, self.leaf_obj())):
            yield self
            if not self.is_leaf():
                for c in self.children():
                    for cr in c.walk(predicate):
                        yield cr

    def query_rect(self, r):
        """ Return things that intersect with 'r'. """
        def p(o,x): return r.does_intersect(o.rect)
        for rr in self.walk(p):
            yield rr

    def query_point(self,point):
        """ Query by a point """
        def p(o,x): return o.rect.does_containpoint(point)
            
        for rr in self.walk(p):
            yield rr

    def lift(self):
        return _NodeCursor(self.root,
                           self.index,
                           self.rect, 
                           self.first_child,
                           self.next_sibling)

    def _become(self, index):
        recti = index * 4
        nodei = index * 2
        rp = self.rpool
        x = rp[recti]
        y = rp[recti+1]
        xx = rp[recti+2]
        yy = rp[recti+3]

        if self.root.kind_pool[index] & EMPTY:
            self.rect = NullRect
        else:
            self.rect = Rect(x,y,xx,yy)

        self.next_sibling = self.npool[nodei]
        self.first_child = self.npool[nodei + 1]
        self.index = index

    def is_leaf(self):
        return bool(self.root.kind_pool[self.index] & LEAF)

    def has_children(self):
        return not self.is_leaf() and 0 != self.first_child

    def holds_leaves(self):
        if 0 == self.first_child: return True
        else:
            return self.has_children() and self.get_first_child().is_leaf()
    
    def get_first_child(self):
        fc = self.first_child
        c = _NodeCursor(self.root,0,NullRect,0,0)
        c._become(self.first_child)
        return c

    def leaf_obj(self):
        if self.is_leaf(): return self.root.leaf_pool[self.first_child]
        else: return None

    def _save_back(self):
        rp = self.rpool
        recti = self.index * 4
        nodei = self.index * 2

        if self.rect is not NullRect:
            self.root.kind_pool[self.index] &= ~EMPTY
            self.rect.write_raw_coords(rp, recti)
        else: 
            self.root.kind_pool[self.index] |= EMPTY
            rp[recti] = 0
            rp[recti+1] = 0
            rp[recti+2] = 0
            rp[recti+3] = 0

        self.npool[nodei] = self.next_sibling
        self.npool[nodei + 1] = self.first_child
    
    def nchildren(self):
        i = self.index
        c = 0
        for x in self.children(): c += 1
        return c

    def insert(self, leafo, leafrect):
        index = self.index

        # tail recursion, made into loop:
        while True:
            if self.holds_leaves():
                self.rect = self.rect.union(leafrect)
                self._insert_child(_NodeCursor.create_leaf(self.root,leafo,leafrect))

                self._balance()
                
                # done: become the original again
                self._become(index)
                return
            else:
                # Not holding leaves, move down a level in the tree:

                # Micro-optimization: 
                #  inlining union() calls -- logic is:
                # ignored,child = min([ ((c.rect.union(leafrect)).area() - c.rect.area(),c.index) for c in self.children() ])
                child = None
                minarea = -1.0
                for c in self.children():
                    x,y,xx,yy = c.rect.coords()
                    lx,ly,lxx,lyy = leafrect.coords()
                    nx = x if x < lx else lx
                    nxx = xx if xx > lxx else lxx
                    ny = y if y < ly else ly
                    nyy = yy if yy > lyy else lyy
                    a = (nxx - nx) * (nyy - ny)
                    if minarea < 0 or a < minarea:
                        minarea = a
                        child = c.index
                # End micro-optimization

                self.rect = self.rect.union(leafrect)
                self._save_back()
                self._become(child) # recurse.
            
    def _balance(self):
        if (self.nchildren() <= MAXCHILDREN):
            return


        t = time.perf_counter()
        
        cur_score = -10

        s_children = [ c.lift() for c in self.children() ]

        memo = {}

        clusterings = [ k_means_cluster(self.root,k,s_children) for k in range(2,MAX_KMEANS) ]
        score,bestcluster = max(((silhouette_coeff(c,memo),c) for c in clusterings),
                                 key=lambda item: item[0])

        nodes = [ _NodeCursor.create_with_children(c,self.root) for c in bestcluster if len(c) > 0]

        self._set_children(nodes)
        
        dur = (time.perf_counter() - t)
        c = float(self.root.stats["overflow_f"]) 
        oa = self.root.stats["avg_overflow_t_f"]
        self.root.stats["avg_overflow_t_f"] = (dur / (c + 1.0)) + (c * oa / (c + 1.0))
        self.root.stats["overflow_f"] += 1
        self.root.stats["longest_overflow"] = max(self.root.stats["longest_overflow"], dur)
            
    def _set_children(self, cs):
        self.first_child = 0

        if 0 == len(cs): 
            return

        pred = None
        for c in cs:
            if pred is not None: 
                pred.next_sibling = c.index
                pred._save_back()
            if 0 == self.first_child:
                self.first_child = c.index
            pred = c
        pred.next_sibling = 0
        pred._save_back()
        self._save_back()

    def _insert_child(self, c):
        c.next_sibling = self.first_child
        self.first_child = c.index
        c._save_back()
        self._save_back()
        

    def children(self):
        # Each child owns a cursor: stopping iteration early must not move
        # the parent (in particular the tree's root cursor).
        if self.is_leaf():
            return
        index = self.first_child
        while index:
            child = _NodeCursor(self.root, 0, NullRect, 0, 0)
            child._become(index)
            index = child.next_sibling
            yield child


def avg_diagonals(node, onodes, memo_tab):
    nidx = node.index
    sv = 0.0
    diag = 0.0
    for onode in onodes:
        k1 = (nidx,onode.index)
        k2 = (onode.index,nidx)
        if k1 in memo_tab: 
            diag = memo_tab[k1]
        elif k2 in memo_tab:
            diag = memo_tab[k2]
        else:
            diag = node.rect.union(onode.rect).diagonal()
            memo_tab[k1] = diag
        
        sv += diag

    return sv / len(onodes)

def silhouette_w(node, cluster, next_closest_cluster, memo):
    ndist = avg_diagonals(node, cluster, memo)
    sdist = avg_diagonals(node, next_closest_cluster, memo)
    scale = max(sdist, ndist)
    return (sdist - ndist) / scale if scale else 0.0

def silhouette_coeff(clustering, memo_tab):
    # special case for a clustering of 1.0
    if (len(clustering) == 1): return 1.0

    coeffs = []
    for cluster in clustering:
        others = [ c for c in clustering if c is not cluster ]
        others_cntr = [ center_of_gravity(c) for c in others ]
        ws = [ silhouette_w(node,cluster,others[closest(others_cntr,node)], memo_tab) for node in cluster ]
        cluster_coeff = sum(ws) / len(ws)
        coeffs.append(cluster_coeff)
    return sum(coeffs) / len(coeffs)

def center_of_gravity(nodes):
    totarea = 0.0
    xs,ys = 0,0
    for n in nodes:
        if n.rect is not NullRect:
            x,y,w,h = n.rect.extent()
            a = w*h
            xs = xs + (a * (x + (0.5 * w)))
            ys = ys + (a * (y + (0.5 * h)))
            totarea = totarea + a
    if totarea:
        return (xs / totarea), (ys / totarea)
    # Points and axis-aligned line rectangles have zero area.
    centers = [((n.rect.x + n.rect.xx) / 2,
                (n.rect.y + n.rect.yy) / 2) for n in nodes
               if n.rect is not NullRect]
    if not centers:
        raise ValueError("Cannot compute the center of an empty cluster")
    return (sum(x for x, y in centers) / len(centers),
            sum(y for x, y in centers) / len(centers))

def closest(centroids, node):
    x,y = center_of_gravity([node])
    dist = -1
    ridx = -1

    for (i,(xx,yy)) in enumerate(centroids):
        dsq = ((xx-x) ** 2) + ((yy-y) ** 2)
        if -1 == dist or dsq < dist:
            dist = dsq
            ridx = i
    return ridx


def k_means_cluster(root, k, nodes):
    t = time.perf_counter()
    if len(nodes) <= k: return [ [n] for n in nodes ]
    
    ns = list(nodes)
    root.stats["count_kmeans_iter_f"] += 1

    # Initialize: take n random nodes.
    random.shuffle(ns)

    cluster_starts = ns[:k]
    cluster_centers = [ center_of_gravity([n]) for n in ns[:k] ]
    
    
    # Bound iteration: area-weighted centers need not converge for every
    # mixture of rectangles and points. Every returned partition is valid.
    for _ in range(MAX_CLUSTER_ITERATIONS):
        root.stats["sum_kmeans_iter_f"] += 1
        clusters = [[] for c in cluster_centers]
        for n in ns:
            clusters[closest(cluster_centers, n)].append(n)
        clusters = [c for c in clusters if c]

        if len(clusters) < 2:
            # Coincident centers must still split the overflowing node.
            clusters = [ns[i::k] for i in range(k)]
            break
        new_cluster_centers = [center_of_gravity(c) for c in clusters]
        if new_cluster_centers == cluster_centers:
            break
        cluster_centers = new_cluster_centers

    root.stats["avg_kmeans_iter_f"] = (root.stats["sum_kmeans_iter_f"] /
                                        root.stats["count_kmeans_iter_f"])
    root.stats["longest_kmeans"] = max(root.stats["longest_kmeans"],
                                      time.perf_counter() - t)
    return clusters
