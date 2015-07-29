"""ClearCenter Marketplace Repository Plug-in

This is a YUM plug-in which dynamically adds marketplace repositories
"""
import os
import re
import httplib
import urllib
import json
import shutil

from urlparse import urlparse
from yum.plugins import PluginYumExit, TYPE_CORE
from yum.yumRepo import YumRepository as Repository
from yum.parser import varReplace
from xml.etree.ElementTree import parse

requires_api_version = '2.3'
plugin_type = (TYPE_CORE,)

class wcRepo:
    def __init__(self, conduit):

        self.conf = conduit.getConf()
        self.url = sdn_url
        self.request = sdn_request
        self.method = sdn_method
        self.basearch = conduit._base.arch.basearch
        self.enable_beta = enable_beta

        if os.getenv('SDN_URL') != None:
            self.url = os.getenv('SDN_URL')
        if os.getenv('SDN_REQUEST') != None:
            self.request = os.getenv('SDN_REQUEST')
        if os.getenv('SDN_METHOD') != None:
            self.method = os.getenv('SDN_METHOD')
        if os.getenv('ENABLE_BETA') != None:
            self.enable_beta = os.getenv('ENABLE_BETA')

        self.organization_vendor = { 'clearcenter.com': 'clear' }

    def parse_kv_line(self, line):
        kv = {}
        rx = re.compile(r'\s*(\w+)\s*=\s*(.*),?')
        for k,v in rx.findall(line):
            if v[-1] == '"':
                v = v[1:-1]
            if '=' in v:
                kv[k] = self.parse_kv_line(self, v)
            else:
                kv[k] = v.rstrip()
        return kv

    def byteify(self, input):
        if isinstance(input, dict):
            return dict([(self.byteify(key), self.byteify(value)) for key, value in input.iteritems()])
        elif isinstance(input, list):
            return [self.byteify(element) for element in input]
        elif isinstance(input, unicode):
            return input.encode('utf-8')
        else:
            return input

    def fetch(self):
        if os.path.exists('/var/clearos/registration/registered') == False:
            raise Exception('check system registration via webconfig...')
            return []

        osvendor = None
        fh = open('/etc/product', 'r')
        lines = fh.readlines()
        fh.close()
        for line in lines:
            kv = self.parse_kv_line(line)
            if not kv.has_key('vendor'):
                continue
            osvendor = kv['vendor']
            break
        if osvendor == None:
            raise Exception('OS vendor not found.')

        hostkey = None
        suva_conf = parse(urllib.urlopen('file:///etc/suvad.conf')).getroot()
        for org in suva_conf.findall('organization'):
            if not self.organization_vendor.has_key(org.attrib.get('name')):
                continue
            if self.organization_vendor[org.attrib.get('name')] != osvendor:
                continue
            hostkey = org.findtext('hostkey')
            break

        if hostkey == None or hostkey == '00000000000000000000000000000000':
            raise Exception('system hostkey not found.')

        osname=None
        osversion=None

        fh = open('/etc/product', 'r')
        lines = fh.readlines()
        fh.close()

        for line in lines:
            kv = self.parse_kv_line(line)
            if not kv.has_key('name'):
                continue
            osname = kv['name']
            break

        if osname == None:
            raise Exception('OS name not found.')

        for line in lines:
            kv = self.parse_kv_line(line)
            if not kv.has_key('version'):
                continue
            osversion = kv['version']
            break

        if osversion == None:
            fh = open('/etc/clearos-release', 'r')
            line = fh.readline()
            fh.close()
            rx = re.compile(r'release\s+([\d\.]+)')
            match = rx.search(line)
            if match != None:
                osversion = match.group(1)

        if osversion == None:
            raise Exception('OS version not found.')

        params = {
            'method': self.method, 'hostkey': hostkey,
            'vendor': osvendor, 'osname': osname, 'osversion': osversion,
            'arch': self.basearch, 'enablebeta': str(self.enable_beta) }
        request = "%s?%s" %(self.request, urllib.urlencode(params))

        hc = httplib.HTTPSConnection(self.url)
        hc.request("GET", request)
        hr = hc.getresponse()
        if hr.status != 200:
            raise Exception('unable to retrieve repository data.')

        buffer = hr.read()
        response = self.byteify(json.loads(buffer))
        if not response.has_key('code') or not response.has_key('repos'):
            raise Exception('malformed repository data response.')

        if response['code'] != 0:
            raise Exception('malformed repository data.')

        repos = []
        baseurl = False
        for r in response['repos']:
            repo = Repository(r['name'])
            repo.yumvar = self.conf.yumvar
            repo.name = varReplace(r['description'], repo.yumvar)

            if 'mirrorlist' in r:
                repo.setAttribute('mirrorlist', varReplace(r['mirrorlist'], repo.yumvar))
            else:
                urls = []
                for u in r['baseurl']:
                    url = varReplace(u['url'], repo.yumvar)
                    if len(u['username']) > 0:
                        url = urlparse(u['url'])
                        port = 80
                        if url.port != None:
                            port = url.port
                        url = "%s://%s:%s@%s:%s%s" %(
                            url.scheme, u['username'], u['password'],
                            url.netloc, port, url.path)
                    if u['url'].find('$basearch') < 0:
                        urls.append(url + '/' + self.basearch)
                repo.setAttribute('baseurl', urls)

            repo.setAttribute('enabled', r['enabled'])
            repo.setAttribute('gpgcheck', r['gpgcheck'])
            if 'sslverify' in r:
                repo.setAttribute('sslverify', r['sslverify'])
            else:
                repo.setAttribute('sslverify', 0)

            if 'header' in r:
                for key, value in r['header'].iteritems():
                    repo.http_headers['X-KEY-%s' % key.upper()] = value

                if not 'everything' in r['header']:
                    repo.setAttribute('includepkgs', ['{0}*'.format(k) for k in r['header'].keys()])

            if 'header' in response:
                repo.http_headers['X-HOSTID'] = hostkey
                for key, value in response['header'].iteritems():
                    repo.http_headers['X-%s' % key.upper()] = value

            repos.append(repo)
        return repos

def config_hook(conduit):
    global sdn_url, sdn_request, sdn_method, enable_beta

    sdn_url = conduit.confString(
        'main', 'sdn_url', default='secure.clearcenter.com')
    sdn_request = conduit.confString(
        'main', 'sdn_request', default='/ws/1.2/marketplace/')
    sdn_method = conduit.confString(
        'main', 'sdn_method', default='get_repo_list')
    enable_beta = conduit.confString(
        'main', 'enable_beta', default='False')

def init_hook(conduit):
    global wc_repos

    conduit.info(2, 'ClearCenter Marketplace: fetching repositories...')

    wc_repo = wcRepo(conduit)
    
    try:
        wc_repos = wc_repo.fetch()
        for r in wc_repos:
            conduit._base.repos.add(r)
    except Exception, msg:
        conduit.info(2, 'ClearCenter Marketplace: %s' %msg)

def close_hook(conduit):
    if 'wc_repos' in globals():
        try:
            for r in wc_repos:
                shutil.rmtree(str(r), True)
        except Exception, msg:
            conduit.info(2, 'ClearCenter Marketplace: %s' %msg)

# vi: expandtab shiftwidth=4 softtabstop=4 tabstop=4
