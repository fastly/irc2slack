#!/usr/local/bin/python

import threading, os, sys, cgi, json, time, traceback, socket, ssl, re
import httplib, urllib, urlparse
import BaseHTTPServer
import ConfigParser

conf = ConfigParser.RawConfigParser()
conf.read('irc2slack.conf')

CA_CERTS_FILE = conf.get('irc', 'ca_certs_file')
HTTP_LISTEN = (conf.get('slack', 'listen_addr'), conf.getint('slack', 'listen_port'))

OUTGOING_TOKENS = [conf.get('slack', 'outgoing_token')]
i = 2
while conf.has_option('slack', 'outgoing_token%d' % (i,)) :
  OUTGOING_TOKENS.append(conf.get('slack', 'outgoing_token%d' % (i,)))
  i += 1

incoming_url =  urlparse.urlparse(conf.get('slack', 'incoming_url'))
assert incoming_url.scheme.lower() == 'https', incoming_url.geturl()
INCOMING_URL_HOST = incoming_url.hostname
INCOMING_URL_PATH = incoming_url.path
if incoming_url.query :
  INCOMING_URL_PATH += '?' + incoming_url.query

IRC_SERVER = (conf.get('irc','server_host'), conf.getint('irc','server_port'))
IRC_NICK = conf.get('irc','nick')
IRC_PASS = conf.get('irc','pass')
if conf.has_option('irc','user') :
  IRC_USER = conf.get('irc','user')
else:
  IRC_USER = IRC_NICK

CHANNEL_IRC2SLACK = {}
for (irc_channel, slack_channel) in conf.items('irc2slack') :
  CHANNEL_IRC2SLACK['#'+irc_channel] = '#'+slack_channel


irc = None
slack = None


def channel_irc2slack(channel):
  return CHANNEL_IRC2SLACK.get(channel)

def channel_slack2irc(channel):
  if not channel.startswith('#') :
    channel = '#' + channel
  for (k, v) in CHANNEL_IRC2SLACK.items() :
    if v == channel :
      return k
  return None


class ToSlack(object):
  def say(self, channel, sender, text):
    body = json.dumps({"channel" : channel, "text": '[%s] %s' % (sender, text)})
    headers = {"Content-type": "application/json"}
    conn = httplib.HTTPSConnection(INCOMING_URL_HOST)
    conn.request("POST", INCOMING_URL_PATH, body, headers)
    response = conn.getresponse()
    data = response.read()
    if response.status != 200 :
      print >> sys.stderr, "Error sending to slack:", response.status, response.reason, repr(data)



class SlackHandler(BaseHTTPServer.BaseHTTPRequestHandler):
  def do_POST(self):
    form = cgi.FieldStorage(
        fp=self.rfile, 
        headers=self.headers,
        environ={'REQUEST_METHOD':'POST',
        'CONTENT_TYPE':self.headers['Content-Type'],
        })
    if form.getvalue('token', None) not in OUTGOING_TOKENS :
      self.send_response(403)
      self.end_headers()
      return

    if form.getvalue('user_id', '') != 'USLACKBOT' :
      self.relay_message(form)

    self.send_response(200)
    self.end_headers()
    self.wfile.write("{}\n");
    return

  def relay_message(self, form):
    slack_channel = form.getvalue('channel_name', 'NONE')
    slack_user = form.getvalue('user_name', 'ANON')
    text = form.getvalue('text', '')

    irc_channel = channel_slack2irc(slack_channel)
    if irc_channel is None :
      return

    if irc is not None :
      irc.say(irc_channel, slack_user, text)


class IRCHandler(threading.Thread):
  def __init__(self):
    threading.Thread.__init__(self)
    self.f = None

  def say(self, channel, sender, text):
    if not text :
      return
    if self.f is None :
      return
    for line in text.replace('\r', '').rstrip().split('\n') :
      self.f.write("PRIVMSG %s :[%s] %s\r\n" % (channel, sender, line))

  def run(self):
    while True:
      try:
        self.run_once()
      except:
        traceback.print_exception(*sys.exc_info())
      print >> sys.stderr, "Retrying in 10s..."
      time.sleep(10)

  def run_once(self):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(IRC_SERVER)
    ss = ssl.wrap_socket(s, cert_reqs=ssl.CERT_REQUIRED, ca_certs=CA_CERTS_FILE, suppress_ragged_eofs=False)
    f = ss.makefile('r+', 0)
    f.write('NICK %s\r\nUSER %s 0 * :Slack Gateway\r\nPASS :%s\r\n' % (IRC_NICK, IRC_USER, IRC_PASS))

    pending_joins = 0
    for chan in CHANNEL_IRC2SLACK.keys() :
      f.write('JOIN %s\r\n' % (chan,))
      pending_joins += 1
    
    while True :
      d = f.readline()
      if d == '' :
        raise EOFError
      d = d.rstrip()
      print >> sys.stderr, 'IRC>', d
      if d.startswith(':') :
        p = d.index(' ')
        snick = d[1:p]
        d = d[p+1:]
        if '!' in snick :
          snick = snick[:snick.index('!')]
        else:
          snick = ''
      else:
        snick = ''
      if d.upper().startswith('PING ') :
        f.write('PONG '+d[len('PING '):]+'\r\n')
      elif d.upper().startswith('PRIVMSG ') :
        (junk, dnick, msg) = d.split(' ', 2)
        if msg.startswith(':') :
          msg = msg[1:]
        if dnick.startswith('#'):
          slack_channel = channel_irc2slack(dnick)
          if slack_channel is not None and slack is not None :
            slack.say(slack_channel, snick, self.remove_escapes(msg))
      elif d.startswith('366 ') :  # RPL_ENDOFNAMES
        pending_joins -= 1

      if self.f is None and pending_joins == 0 :
        print >> sys.stderr, 'Finished joining'
        self.f = f

  def remove_escapes(self, msg):
    return re.compile(r'[\x02\x0f\x16\x1f]|\x03\d{1,2}(,\d{1,2})?').sub('', msg)

if __name__ == "__main__" :
  try:
    slack = ToSlack()

    irc = IRCHandler()
    irc.start()

    httpd = BaseHTTPServer.HTTPServer(HTTP_LISTEN, SlackHandler)
    httpd.serve_forever()
  except KeyboardInterrupt:
    os._exit(1)

# vim: set et sw=2 ts=2:
