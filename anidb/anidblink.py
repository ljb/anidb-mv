import socket,sys,zlib
from time import time,sleep
from Crypto.Cipher.AES import new as aes
from md5 import md5
from hashes import pkcs5padding_pad,pkcs5padding_strip
from threading import Thread
from responses import ResponseResolver

class AniDBLink(Thread):
	def __init__(self,server,port,myport,delay=2,timeout=20):
		Thread.__init__(self)
		self.server=server
		self.port=port
		self.target=(server,port)
		self.sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
		
		self.sock.bind(('',myport))
		self.sock.settimeout(timeout)

		self.cmd_queue={None:None}
		self.resp_tagged_queue={}
		self.resp_untagged_queue=[]
		self.tags=[]
		self.lastpacket=0
		self.delay=delay
		self.timeout=timeout
		self.session=None
		self.banned=False
		self.crypt=None

		self.setDaemon(True)
		self.start()
	
	def run(self):
		while 1:
			try:
				data=self.sock.recv(8192)
			except socket.timeout:
				self._handle_timeouts()
				continue
			print "NetIO < %s"%repr(data)
			try:
				for i in range(2):
					try:
						tmp=data
						resp=None
						if self.crypt:
							tmp=self.crypt.decrypt(tmp)
							tmp=pkcs5padding_strip(tmp)
							print "DeCry | %s"%repr(tmp)
						if tmp[:2]=='\x00\x00':
							tmp=zlib.decompressobj().decompress(tmp[2:])
							print "UnZip | %s"%repr(tmp)
						resp=ResponseResolver(tmp)
					except:
						sys.excepthook(*sys.exc_info())
						self.crypt=None
						self.session=None
					else:
						break
				if not resp:
					raise AniDBPacketCorrupted,"Either decrypting, decompressing or parsing the packet failed"
				cmd=self._cmd_dequeue(resp)
				resp=resp.resolve(cmd)
				resp.parse()
				if resp.rescode in ('200','201'):
					self.session=resp.attrs['sesskey']
				if resp.rescode in ('209',):
					self.crypt=aes(md5(resp.req.apipassword+resp.attrs['salt']).digest())
				if resp.rescode in ('203','403','500','501','503','506'):
					self.session=None
					self.crypt=None
				if resp.rescode in ('504','555'):
					self.banned=True
					print "AniDB API informs that user or client is banned:",resp.resstr
				resp.handle()
				if not cmd or not cmd.mode:
					self._resp_queue(resp)
				else:
					self.tags.remove(resp.restag)
			except:
				sys.excepthook(*sys.exc_info())
				print "Avoiding flood by paranoidly panicing: Aborting link thread, killing connection, releasing waiters and quiting"
				self.sock.close()
				try:cmd.waiter.release()
				except:pass
				for tag,cmd in self.cmd_queue.iteritems():
					try:cmd.waiter.release()
					except:pass
				sys.exit()
	
	def _handle_timeouts(self):
		willpop=[]
		for tag,cmd in self.cmd_queue.iteritems():
			if not tag:
				continue
			if time()-cmd.started>self.timeout:
				self.tags.remove(cmd.tag)
				willpop.append(cmd.tag)
				cmd.waiter.release()

		for tag in willpop:
			self.cmd_queue.pop(tag)
	
	def _resp_queue(self,response):
		if response.restag:
			self.resp_tagged_queue[response.restag]=response
		else:
			self.resp_untagged_queue.append(response)
	
	def getresponse(self,command):
		if command:
			resp=self.resp_tagged_queue.pop(command.tag)
		else:
			resp=self.resp_untagged_queue.pop()
		self.tags.remove(resp.restag)
		return resp
	
	def _cmd_queue(self,command):
		self.cmd_queue[command.tag]=command
		self.tags.append(command.tag)
	
	def _cmd_dequeue(self,resp):
		if not resp.restag:
			return None
		else:
			return self.cmd_queue.pop(resp.restag)
	
	def _delay(self):
		return (self.delay<2 and 2 or self.delay)
	
	def _send(self,command):
		if self.banned:
			print "NetIO | BANNED"
			raise AniDBError,"Not sending, banned"
		if time()-self.lastpacket<self._delay():
			sleep(self._delay()-(time()-self.lastpacket))
		self.lastpacket=time()
		command.started=time()
		data=command.raw_data()
		if self.crypt:
			print "EnCry | %s"%repr(data)
			data=pkcs5padding_pad(data)
			data=self.crypt.encrypt(data)
		self.sock.sendto(data,self.target)
		print "NetIO > %s"%repr(data)
	
	def new_tag(self):
		if not len(self.tags):
			maxtag="T000"
		else:
			maxtag=max(self.tags)
		newtag="T%03d"%(int(maxtag[1:])+1)
		return newtag
	
	def request(self,command):
		if not (self.session and command.session) and command.command not in ('AUTH','PING','ENCRYPT'):
			raise AniDBMustAuthError,"You must be authed to execute commands besides AUTH and PING"
		command.started=time()
		self._cmd_queue(command)
		self._send(command)

