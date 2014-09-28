from threading import Lock
from responses import *
from errors import *

class Command:
	queue={None:None}
	def __init__(self,command,**parameters):
		self.command=command
		self.parameters=parameters
		self.raw=self.flatten(command,parameters)

		self.mode=None
		self.callback=None
		self.waiter=Lock()
		self.waiter.acquire()
	
	def __repr__(self):
		return "Command(%s,%s) %s\n%s\n"%(repr(self.tag),repr(self.command),repr(self.parameters),self.raw_data())
	
	def authorize(self,mode,tag,session,callback):
		self.mode=mode
		self.callback=callback
		self.tag=tag
		self.session=session
		
		self.parameters['tag']=tag
		self.parameters['s']=session
	
	def handle(self,resp):
		self.resp=resp
		if self.mode==1:
			self.waiter.release()
		elif self.mode==2:
			self.callback(resp)
	
	def wait_response(self):
		self.waiter.acquire()
	
	def flatten(self,command,parameters):
		tmp=[]
		for key,value in parameters.iteritems():
			if value==None:
				continue
			tmp.append("%s=%s"%(self.escape(key),self.escape(value)))
		return ' '.join([command,'&'.join(tmp)])
	
	def escape(self,data):
		return str(data).replace('&','&amp;')
	
	def raw_data(self):
		self.raw=self.flatten(self.command,self.parameters)
		return self.raw
		
	def cached(self,interface,database):
		return None
	
	def cache(self,interface,database):
		pass
		
#first run
class AuthCommand(Command):
	def __init__(self,username,password,protover,client,clientver,nat=None,comp=None,enc=None,mtu=None):
		parameters={'user':username,'pass':password,'protover':protover,'client':client,'clientver':clientver,'nat':nat,'comp':comp,'enc':enc,'mtu':mtu}
		Command.__init__(self,'AUTH',**parameters)

class LogoutCommand(Command):
	def __init__(self):
		Command.__init__(self,'LOGOUT')

#third run (at the same time as second)
class PushCommand(Command):
	def __init__(self,notify,msg,buddy=None):
		parameters={'notify':notify,'msg':msg,'buddy':buddy}
		Command.__init__(self,'PUSH',**parameters)

class PushAckCommand(Command):
	def __init__(self,nid):
		parameters={'nid':nid}
		Command.__init__(self,'PUSHACK',**parameters)

class NotifyCommand(Command):
	def __init__(self,buddy=None):
		parameters={'buddy':buddy}
		Command.__init__(self,'NOTIFY',**parameters)

class NotifyListCommand(Command):
	def __init__(self):
		Command.__init__(self,'NOTIFYLIST')

class NotifyGetCommand(Command):
	def __init__(self,type,id):
		parameters={'type':type,'id':id}
		Command.__init__(self,'NOTIFYGET',**parameters)

class NotifyAckCommand(Command):
	def __init__(self,type,id):
		parameters={'type':type,'id':id}
		Command.__init__(self,'NOTIFYACK',**parameters)

class BuddyAddCommand(Command):
	def __init__(self,uid=None,uname=None):
		if not (uid or uname) or (uid and uname):
			raise AniDBIncorrectParameterError,"You must provide <u(id|name)> for BUDDYADD command"
		parameters={'uid':uid,'uname':uname.lower()}
		Command.__init__(self,'BUDDYADD',**parameters)

class BuddyDelCommand(Command):
	def __init__(self,uid):
		parameters={'uid':uid}
		Command.__init__(self,'BUDDYDEL',**parameters)

class BuddyAcceptCommand(Command):
	def __init__(self,uid):
		parameters={'uid':uid}
		Command.__init__(self,'BUDDYACCEPT',**parameters)

class BuddyDenyCommand(Command):
	def __init__(self,uid):
		parameters={'uid':uid}
		Command.__init__(self,'BUDDYDENY',**parameters)

class BuddyListCommand(Command):
	def __init__(self,startat):
		parameters={'startat':startat}
		Command.__init__(self,'BUDDYLIST',**parameters)

class BuddyStateCommand(Command):
	def __init__(self,startat):
		parameters={'startat':startat}
		Command.__init__(self,'BUDDYSTATE',**parameters)

#first run
class AnimeCommand(Command):
	def __init__(self,aid=None,aname=None,acode=None):
		if not (aid or aname) or (aid and aname):
			raise AniDBIncorrectParameterError,"You must provide <a(id|name)> for ANIME command"
		parameters={'aid':aid,'aname':aname,'acode':acode}
		Command.__init__(self,'ANIME',**parameters)
	
	def cached(self,intr,db):
		aid=self.parameters['aid']
		aname=self.parameters['aname']
		
		names=','.join([code for code in AnimeResponse.acodes if code!=''])
		ruleholder=(aid and 'aid=%s' or 'name=%s OR romaji=%s OR kanji=%s OR othername=%s OR shortnames RLIKE %s OR synonyms RLIKE %s')
		rulevalues=(aid and [aid] or [aname,aname,aname,aname,"('|^)"+aname+"('|$)","('|^)"+aname+"('|$)"])
		
		rows=db.select('atb',names,ruleholder,*rulevalues)
		
		if len(rows)>1:
			raise AniDBInternalError,"It shouldn't be possible for database to return more than 1 line for ANIME cache"
		elif not len(rows):
			return None
		else:
			self.parameters['acode']=-1
			resp=AnimeResponse(self,None,'230','CACHED ANIME',[list(rows[0])])
			resp.parse()
			return resp
		
	def cache(self,intr,db):
		acode=self.parameters['acode']
		acode=acode and int(acode) or acode
		if self.resp.rescode!='230' or self.cached(intr,db) or acode!=-1:
			return

		names='status,'+','.join([code for code in AnimeResponse.acodes if code!=''])
		valueholders='0,'+','.join(['%s'for code in AnimeResponse.acodes if code!=''])
		values=[self.resp.datalines[0][code] for code in AnimeResponse.acodes if code!='']
		
		db.insert('atb',names,valueholders,*values)

class EpisodeCommand(Command):
	def __init__(self,eid=None,aid=None,aname=None,epno=None):
		if not (eid or ((aname or aid) and epno)) or (aname and aid) or (eid and (aname or aid or epno)):
			raise AniDBIncorrectParameterError,"You must provide <eid XOR a(id|name)+epno> for EPISODE command"
		parameters={'eid':eid,'aid':aid,'aname':aname,'epno':epno}
		Command.__init__(self,'EPISODE',**parameters)
	
	def cached(self,intr,db):
		eid=self.parameters['eid']
		aid=self.parameters['aid']
		aname=self.parameters['aname']
		epno=self.parameters['epno']

		names="eid,aid,length,rating,votes,epno,name,romaji,kanji"
		if eid:
			ruleholder="eid=%s"
			rulevalues=[eid]
		else:
			resp=intr.anime(aid=aid,aname=aname,acode=-1)
			if resp.rescode!='230':
				#print "EPISODECACHE: Anime specification seems to be invalid, good luck have fun"
				#return None
				resp=NoSuchEpisodeResponse(self,None,'340','NO SUCH EPISODE (ANIME NOT FOUND)',[])
				resp.parse()
				return resp
			aid=resp.datalines[0]['aid']
			
			ruleholder="aid=%s AND epno=%s"
			rulevalues=[aid,epno]
		
		rows=db.select('etb',names,ruleholder,*rulevalues)

		if len(rows)>1:
			raise AniDBInternalError,"It shouldn't be possible for database to return more than 1 line for EPISODE cache"
		elif not len(rows):
			return None
		else:
			resp=EpisodeResponse(self,None,'240','CACHED EPISODE',[list(rows[0])])
			resp.parse()
			return resp
	
	def cache(self,intr,db):
		if self.resp.rescode!='240' or self.cached(intr,db):
			return

		codes=('eid','aid','length','rating','votes','epno','name','romaji','kanji')
		names='status,'+','.join([code for code in codes if code!=''])
		valueholders='0,'+','.join(['%s'for code in codes if code!=''])
		values=[self.resp.datalines[0][code] for code in codes if code!='']

		db.insert('etb',names,valueholders,*values)

class FileCommand(Command):
	def __init__(self,fid=None,size=None,ed2k=None,aid=None,aname=None,gid=None,gname=None,epno=None,fcode=None,acode=None):
		if not (fid or (size and ed2k) or ((aid or aname) and (gid or gname) and epno)) or (fid and (size or ed2k or aid or aname or gid or gname or epno)) or ((size and ed2k) and (fid or aid or aname or gid or gname or epno)) or (((aid or aname) and (gid or gname) and epno) and (fid or size or ed2k)) or (aid and aname) or (gid and gname):
			raise AniDBIncorrectParameterError,"You must provide <fid XOR size+ed2k XOR a(id|name)+g(id|name)+epno> for FILE command"
		parameters={'fid':fid,'size':size,'ed2k':ed2k,'aid':aid,'aname':aname,'gid':gid,'gname':gname,'epno':epno,'fcode':fcode,'acode':acode}
		Command.__init__(self,'FILE',**parameters)
	
	def cached(self,intr,db):
		fid=self.parameters['fid']
		size=self.parameters['size']
		ed2k=self.parameters['ed2k']
		aid=self.parameters['aid']
		aname=self.parameters['aname']
		gid=self.parameters['gid']
		gname=self.parameters['gname']
		epno=self.parameters['epno']
		acode=self.parameters['acode']
		fcode=self.parameters['fcode']
		acode=acode and int(acode) or acode
		fcode=fcode and int(fcode) or fcode

		if acode!=0:#we won't support querying all the information for now..
			return None

		names=','.join([code for code in ('fid',)+FileResponse.fcodes if code!=''])
		
		if fid:
			ruleholder="fid=%s"
			rulevalues=[fid]
		elif size and ed2k:
			ruleholder="size=%s AND ed2k=%s"
			rulevalues=[size,ed2k]
		else:
			resp=intr.anime(aid=aid,aname=aname,acode=-1)
			if resp.rescode!='230':
				resp=NoSuchFileResponse(self,None,'320','NO SUCH FILE (ANIME NOT FOUND)',[])
				resp.parse()
				return resp
			aid=resp.datalines[0]['aid']

			resp=intr.group(gid=gid,gname=gname)
			if resp.rescode!='250':
				resp=NoSuchFileResponse(self,None,'320','NO SUCH FILE (GROUP NOT FOUND)',[])
				resp.parse()
				return resp
			gid=resp.datalines[0]['gid']

			resp=intr.episode(aid=aid,epno=epno)
			if resp.rescode!='240':
				resp=NoSuchFileResponse(self,None,'320','NO SUCH FILE (EPISODE NOT FOUND)',[])
				resp.parse()
				return resp
			eid=resp.datalines[0]['eid']

			ruleholder="aid=%s AND eid=%s AND gid=%s"
			rulevalues=[aid,eid,gid]

		rows=db.select('ftb',names,ruleholder,*rulevalues)

		if len(rows)>1:
			#resp=MultipleFilesFoundResponse(self,None,'322','CACHED MULTIPLE FILES FOUND',/*get fids from rows, not gonna do this as you haven't got a real cache out of these..*/)
			return None
		elif not len(rows):
			return None
		else:
			self.parameters['fcode']=-1
			resp=FileResponse(self,None,'220','CACHED FILE',[list(rows[0])])
			resp.parse()
			return resp
	
	def cache(self,intr,db):
		fcode=self.parameters['fcode']
		fcode=fcode and int(fcode) or fcode
		if self.resp.rescode!='220' or self.cached(intr,db) or fcode!=-1:
			return
			
		names='status,'+','.join([code for code in ('fid',)+FileResponse.fcodes if code!=''])
		valueholders='0,'+','.join(['%s'for code in ('fid',)+FileResponse.fcodes if code!=''])
		values=[self.resp.datalines[0][code] for code in ('fid',)+FileResponse.fcodes if code!='']

		db.insert('ftb',names,valueholders,*values)

class GroupCommand(Command):
	def __init__(self,gid=None,gname=None):
		if not (gid or gname) or (gid and gname):
			raise AniDBIncorrectParameterError,"You must provide <g(id|name)> for GROUP command"
		parameters={'gid':gid,'gname':gname}
		Command.__init__(self,'GROUP',**parameters)
	
	def cached(self,intr,db):
		gid=self.parameters['gid']
		gname=self.parameters['gname']
		
		codes=('gid', 'rating', 'votes', 'animes', 'files', 'name', 'shortname', 'ircchannel', 'ircserver', 'url')
		names=','.join([code for code in codes if code!=''])
		ruleholder=(gid and 'gid=%s' or 'name=%s OR shortname=%s')
		rulevalues=(gid and [gid] or [gname,gname])
		
		rows=db.select('gtb',names,ruleholder,*rulevalues)
		
		if len(rows)>1:
			raise AniDBInternalError,"It shouldn't be possible for database to return more than 1 line for GROUP cache"
		elif not len(rows):
			return None
		else:
			resp=GroupResponse(self,None,'250','CACHED GROUP',[list(rows[0])])
			resp.parse()
			return resp
		
	def cache(self,intr,db):
		if self.resp.rescode!='250' or self.cached(intr,db):
			return

		codes=('gid', 'rating', 'votes', 'animes', 'files', 'name', 'shortname', 'ircchannel', 'ircserver', 'url')
		names='status,'+','.join([code for code in codes if code!=''])
		valueholders='0,'+','.join(['%s'for code in codes if code!=''])
		values=[self.resp.datalines[0][code] for code in codes if code!='']
		
		db.insert('gtb',names,valueholders,*values)
	

class ProducerCommand(Command):
	def __init__(self,pid=None,pname=None):
		if not (pid or pname) or (pid and pname):
			raise AniDBIncorrectParameterError,"You must provide <p(id|name)> for PRODUCER command"
		parameters={'pid':pid,'pname':pname}
		Command.__init__(self,'PRODUCER',**parameters)
	
	def cached(self,intr,db):
		pid=self.parameters['pid']
		pname=self.parameters['pname']
		
		codes=('pid', 'name', 'shortname', 'othername', 'type', 'pic', 'url')
		names=','.join([code for code in codes if code!=''])
		ruleholder=(pid and 'pid=%s' or 'name=%s OR shortname=%s OR othername=%s')
		rulevalues=(pid and [pid] or [pname,pname,pname])
		
		rows=db.select('ptb',names,ruleholder,*rulevalues)
		
		if len(rows)>1:
			raise AniDBInternalError,"It shouldn't be possible for database to return more than 1 line for PRODUCER cache"
		elif not len(rows):
			return None
		else:
			resp=ProducerResponse(self,None,'245','CACHED PRODUCER',[list(rows[0])])
			resp.parse()
			return resp
		
	def cache(self,intr,db):
		if self.resp.rescode!='245' or self.cached(intr,db):
			return

		codes=('pid', 'name', 'shortname', 'othername', 'type', 'pic', 'url')
		names='status,'+','.join([code for code in codes if code!=''])
		valueholders='0,'+','.join(['%s'for code in codes if code!=''])
		values=[self.resp.datalines[0][code] for code in codes if code!='']
		
		db.insert('ptb',names,valueholders,*values)

class MyListCommand(Command):
	def __init__(self,lid=None,fid=None,size=None,ed2k=None,aid=None,aname=None,gid=None,gname=None,epno=None):
		if not (lid or fid or (size and ed2k) or (aid or aname)) or (lid and (fid or size or ed2k or aid or aname or gid or gname or epno)) or (fid and (lid or size or ed2k or aid or aname or gid or gname or epno)) or ((size and ed2k) and (lid or fid or aid or aname or gid or gname or epno)) or ((aid or aname) and (lid or fid or size or ed2k)) or (aid and aname) or (gid and gname):
			raise AniDBIncorrectParameterError,"You must provide <lid XOR fid XOR size+ed2k XOR a(id|name)+g(id|name)+epno> for MYLIST command"
		parameters={'lid':lid,'fid':fid,'size':size,'ed2k':ed2k,'aid':aid,'aname':aname,'gid':gid,'gname':gname,'epno':epno}
		Command.__init__(self,'MYLIST',**parameters)

class MyListAddCommand(Command):
	def __init__(self,lid=None,fid=None,size=None,ed2k=None,aid=None,aname=None,gid=None,gname=None,epno=None,edit=None,state=None,viewed=None,viewdate=None,source=None,storage=None,other=None):
		if not (lid or fid or (size and ed2k) or ((aid or aname) and (gid or gname))) or (lid and (fid or size or ed2k or aid or aname or gid or gname or epno)) or (fid and (lid or size or ed2k or aid or aname or gid or gname or epno)) or ((size and ed2k) and (lid or fid or aid or aname or gid or gname or epno)) or (((aid or aname) and (gid or gname)) and (lid or fid or size or ed2k)) or (aid and aname) or (gid and gname) or (lid and not edit):
			raise AniDBIncorrectParameterError,"You must provide <lid XOR fid XOR size+ed2k XOR a(id|name)+g(id|name)+epno> for MYLISTADD command"
		parameters={'lid':lid,'fid':fid,'size':size,'ed2k':ed2k,'aid':aid,'aname':aname,'gid':gid,'gname':gname,'epno':epno,'edit':edit,'state':state,'viewed':viewed, 'viewdate':viewdate, 'source':source,'storage':storage,'other':other}
		Command.__init__(self,'MYLISTADD',**parameters)

class MyListDelCommand(Command):
	def __init__(self,lid=None,fid=None,aid=None,aname=None,gid=None,gname=None,epno=None):
		if not (lid or fid or ((aid or aname) and (gid or gname) and epno)) or (lid and (fid or aid or aname or gid or gname or epno)) or (fid and (lid or aid or aname or gid or gname or epno)) or (((aid or aname) and (gid or gname) and epno) and (lid or fid)) or (aid and aname) or (gid and gname):
			raise AniDBIncorrectParameterError,"You must provide <lid+edit=1 XOR fid XOR a(id|name)+g(id|name)+epno> for MYLISTDEL command"
		parameters={'lid':lid,'fid':fid,'aid':aid,'aname':aname,'gid':gid,'gname':gname,'epno':epno}
		Command.__init__(self,'MYLISTDEL',**parameters)

class MyListStatsCommand(Command):
	def __init__(self):
		Command.__init__(self,'MYLISTSTATS')

class VoteCommand(Command):
	def __init__(self,type,id=None,name=None,value=None,epno=None):
		if not (id or name) or (id and name):
			raise AniDBIncorrectParameterError,"You must provide <(id|name)> for VOTE command"
		parameters={'type':type,'id':id,'name':name,'value':value,'epno':epno}
		Command.__init__(self,'VOTE',**parameters)

class RandomAnimeCommand(Command):
	def __init__(self,type):
		parameters={'type':type}
		Command.__init__(self,'RANDOMANIME',**parameters)

class PingCommand(Command):
	def __init__(self):
		Command.__init__(self,'PING')

#second run
class EncryptCommand(Command):
	def __init__(self,user,apipassword,type):
		self.apipassword=apipassword
		parameters={'user':user.lower(),'type':type}
		Command.__init__(self,'ENCRYPT',**parameters)

class EncodingCommand(Command):
	def __init__(self,name):
		parameters={'name':type}
		Command.__init__(self,'ENCODING',**parameters)

class SendMsgCommand(Command):
	def __init__(self,to,title,body):
		if len(title)>50 or len(body)>900:
			raise AniDBIncorrectParameterError,"Title must not be longer than 50 chars and body must not be longer than 900 chars for SENDMSG command"
		parameters={'to':to.lower(),'title':title,'body':body}
		Command.__init__(self,'SENDMSG',**parameters)

class UserCommand(Command):
	def __init__(self,user):
		parameters={'user':user}
		Command.__init__(self,'USER',**parameters)

class UptimeCommand(Command):
	def __init__(self):
		Command.__init__(self,'UPTIME')

class VersionCommand(Command):
	def __init__(self):
		Command.__init__(self,'VERSION')

