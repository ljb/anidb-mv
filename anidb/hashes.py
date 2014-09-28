from Crypto.Hash.MD4 import new as md4_new
from Crypto.Hash.MD5 import new as md5_new
from Crypto.Hash.SHA import new as sha1_new
from binascii import crc32 as crc32_func
from threading import Thread
import os

def pkcs5padding_pad(data):
	bytes=(16-(len(data)%16))
	return data+(bytes*chr(bytes))

def pkcs5padding_strip(data):
	bytes=ord(data[-1])
	for byte in data[-bytes:]:
		if ord(byte)!=bytes:
			raise ValueError,"depadding failed"
	return data[:-bytes]

class ed2k_new:
	def __init__(self,l):
		self.l=l
		self.m=9728000
		self.h=""
	
	def update(self,c):
		if self.l<=self.m:
			self.h=c
		else:
			self.h+=md4_new(c).digest()

	def hexdigest(self):
		return md4_new(self.h).hexdigest()

def ed2k_newer(l):
	return lambda: ed2k_new(l)

class crc32_new:
	def __init__(self):
		self.old=0
	
	def update(self,data):
		self.old=crc32_func(data,self.old)
	
	def hexdigest(self):
		return "%08x"%(self.old<0 and 2**32+self.old or self.old)

def calc_hashes(hashes,name,cb=None):
	f=file(name)
	m=9728000
	l=os.fstat(f.fileno()).st_size
	a={'ed2k':ed2k_newer(l),'md5':md5_new,'sha1':sha1_new,'crc32':crc32_new}
	h={}
	for n in hashes:
		h[n]=a[n]()
	
	i=None
	g=0.0
	while 1:
		(cb and g<l and cb(g/l*100))
		c=f.read(m)
		g+=m
		if not c: break
		(i and i.join())
		i=do_calc(h,c)
	(i and i.join())
	(cb and cb(100.0))
	
	t={}
	for n,o in h.iteritems():
		t[n]=o.hexdigest()
	return t

class do_calc(Thread):
	def __init__(self,h,c):
		Thread.__init__(self)
		self.h=h
		self.c=c
		self.start()
	
	def run(self):
		for o in self.h.values():
			o.update(self.c)

