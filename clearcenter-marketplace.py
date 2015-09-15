"""ClearCenter Marketplace Repository Plug-in

This is a YUM plug-in which dynamically adds marketplace repositories
"""
import os
import re
import httplib
import urllib
import json
import shutil
import random
import urlgrabber
import time

from urlparse import urlparse
from yum.plugins import PluginYumExit, TYPE_CORE
from yum.yumRepo import YumRepository as Repository
from yum.parser import varReplace
from xml.etree.ElementTree import parse
from iniparse import INIConfig

requires_api_version = '2.3'
plugin_type = (TYPE_CORE,)

def touch(filename):
    with open(filename, 'a'):
        os.utime(filename, time.time())

def update_repo_file(filename, section_id, name, value):
    ini = INIConfig(open(filename))

    if section_id not in ini._sections:
        for sect in ini._sections.keys():
            if varReplace(sect, yumvar) == section_id:
                section_id = sect

    if (name in ini[section_id]):
        ini[section_id][name] = value

    fp = file(filename, "w")
    fp.write(str(ini))
    fp.close()

def enable_repo(repos, enable=True):
    for repo in sorted(repos):
        if enable:
            repo.enable()
        else:
            repo.disable()

        update_repo_file(repo.repofile, repo.id, 'enabled', (1 if enable else 0))

class wcRepo:
    def __init__(self, conduit):
        global enable_beta
        global jws_domain, jws_method, jws_nodes, jws_prefix, jws_prefix, jws_realm
        global jws_request, jws_version, enable_beta

        self.conf = conduit.getConf()
        self.basearch = conduit._base.arch.basearch
        self.yum_repos = conduit.getRepos()
        self.organization_vendor = { 'clearcenter.com': 'clear' }

        self.enable_beta = enable_beta

        if os.getenv('ENABLE_BETA') != None:
            self.enable_beta = os.getenv('ENABLE_BETA')

        self.product_lines = ''

        try:
            fh = open('/etc/product', 'r')
            self.product_lines = fh.readlines()
            fh.close()
        except:
            pass

        for line in self.product_lines:
            kv = self.parse_kv_line(line)
            if not kv.has_key('jws_domain'):
                continue
            jws_domain = kv['jws_domain']
            break

        for line in self.product_lines:
            kv = self.parse_kv_line(line)
            if not kv.has_key('jws_method'):
                continue
            jws_method = kv['jws_method']
            break

        for line in self.product_lines:
            kv = self.parse_kv_line(line)
            if not kv.has_key('jws_nodes'):
                continue
            jws_nodes = int(kv['jws_nodes'])
            break

        for line in self.product_lines:
            kv = self.parse_kv_line(line)
            if not kv.has_key('jws_prefix'):
                continue
            jws_prefix = kv['jws_prefix']
            break

        for line in self.product_lines:
            kv = self.parse_kv_line(line)
            if not kv.has_key('jws_realm'):
                continue
            jws_realm = kv['jws_realm']
            break

        for line in self.product_lines:
            kv = self.parse_kv_line(line)
            if not kv.has_key('jws_request'):
                continue
            jws_request = kv['jws_request']
            break

        for line in self.product_lines:
            kv = self.parse_kv_line(line)
            if not kv.has_key('jws_version'):
                continue
            jws_version = kv['jws_version']
            break

        random.seed()
        self.url = "%s%d.%s" %(jws_prefix, random.randint(1, jws_nodes), jws_domain)
        self.request = "/%s/%s/%s" %(jws_realm, jws_version, jws_request)

    def parse_kv_line(self, line):
        kv = {}
        rx = re.compile(r'\s*(\w+)\s*=\s*(.*),?')
        for k, v in rx.findall(line):
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
        global jws_method, osvendor

        osname=None
        osversion=None
        software_id=0

        for line in self.product_lines:
            kv = self.parse_kv_line(line)
            if not kv.has_key('vendor'):
                continue
            osvendor = kv['vendor']
            break

        for line in self.product_lines:
            kv = self.parse_kv_line(line)
            if not kv.has_key('name'):
                continue
            osname = kv['name']
            break

        for line in self.product_lines:
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

        for line in self.product_lines:
            kv = self.parse_kv_line(line)
            if not kv.has_key('software_id'):
                continue
            software_id = kv['software_id']
            break

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

        params = {
            'method': jws_method, 'hostkey': hostkey,
            'vendor': osvendor, 'osname': osname, 'osversion': osversion,
            'arch': self.basearch, 'enablebeta': str(self.enable_beta),
            'software_id': software_id
        }

        request = "%s?%s" %(self.request, urllib.urlencode(params))

        hc = httplib.HTTPSConnection(self.url)
        hc.request("GET", request)
        hr = hc.getresponse()
        if hr.status != 200:
            raise Exception('unable to retrieve repository data.')

        buffer = hr.read()
        hc.close()
        response = self.byteify(json.loads(buffer))

        if not response.has_key('code'):
            raise Exception('malformed response.')

        if response['code'] != 0:
            if not response.has_key('errmsg'):
                raise Exception('request failed, error code: %d' %(response['code']))
            else:
                raise Exception('%s Code: %d' %(response['errmsg'], response['code']))

        if not os.path.isfile('/var/clearos/registration/verified') and response.has_key('community') and response['community'] == 1:
            repos_to_enable = self.yum_repos.findRepos(
                'clearos-centos,clearos-centos-updates,clearos-epel,clearos-updates',
                name_match=True, ignore_case=True)
            enable_repo(repos_to_enable)
            touch('/var/clearos/registration/verified')

        if not response.has_key('repos'):
            raise Exception('malformed response, missing repos.')

        repos = []
        baseurl = False
        for r in response['repos']:
            repo = Repository(r['name'])
            baserepo = re.sub(r'^clearos-(.*?)(-testing)?$', r'\1', r['name'])
            repo.yumvar = self.conf.yumvar
            repo.name = varReplace(r['description'], repo.yumvar)
            repo.basecachedir = self.conf.cachedir
            repo.base_persistdir = self.conf._repos_persistdir

            if 'mirrorlist' in r:
                repo.setAttribute('mirrorlist',
                    varReplace(r['mirrorlist'], repo.yumvar))
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
                    else:
                        urls.append(url)
                repo.setAttribute('baseurl', urls)

            repo.setAttribute('enabled', r['enabled'])
            repo.setAttribute('gpgcheck', r['gpgcheck'])
            if 'gpgkey' in r:
                repo.setAttribute('gpgkey', varReplace(r['gpgkey'], repo.yumvar))
            if 'sslverify' in r:
                repo.setAttribute('sslverify', r['sslverify'])
            else:
                repo.setAttribute('sslverify', 0)

            if not r['name'].startswith('private-'):
                headers = r.get('header', {})
                headers.update(response.get('header', {}))
                if 'expire' in headers:
                    headers['hostid'] = hostkey

                pkgkeys = True
                pkg_headers = {}
                pkgs = []
                for key, value in headers.iteritems():
                    if key in ['hostid', 'expire', 'key']:
                        repo.http_headers['X-%s' % key.upper()] = value
                    elif key in ['everyting', baserepo]:
                        pkgkeys = False
                        repo.http_headers['X-KEY-%s' % key.upper()] = value
                    else:
                        pkgs += [key]
                        pkg_headers['X-KEY-%s' % key.upper()] = value

                if pkgkeys:
                    repo.http_headers.update(pkg_headers)
                    group = re.sub(r'^clearos-', r'', r['name'])
                    request = '/pkgapi/%s/%s' % (osversion[:1], group)

                    try:
                        hc = httplib.HTTPSConnection('mirrorlist.clearos.com')
                        hc.request("GET", request, None, repo.http_headers)
                        hr = hc.getresponse()
                        if hr.status != 200:
                            raise Exception('unable to retrieve repository data.')

                        incpkgs = hr.read()
                        hc.close()
                        repo.setAttribute('includepkgs', incpkgs.split())
                    except:
                        pass

                    if not repo.includepkgs:
                        repo.setAttribute('includepkgs', ['None'])

            repos.append(repo)
        return repos

def config_hook(conduit):
    global enable_beta
    global jws_domain, jws_method, jws_nodes, jws_prefix, jws_prefix, jws_realm
    global jws_request, jws_version, enable_beta, osvendor

    enable_beta = conduit.confBool('main', 'enable_beta', default=False)
    osvendor = conduit.confString('main', 'osvendor', default='clear')

    jws_domain = conduit.confString('jws', 'domain', default='clearsdn.com')
    jws_method = conduit.confString('jws', 'method', default='get_repo_list')
    jws_nodes = conduit.confInt('jws', 'nodes', default=1)
    jws_prefix = conduit.confString('jws', 'prefix', default='cos7-ws')
    jws_realm = conduit.confString('jws', 'realm', default='ws')
    jws_request = conduit.confString('jws', 'request', default='marketplace/index.jsp')
    jws_version = conduit.confString('jws', 'version', default='1.2')

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
                shutil.rmtree(r.pkgdir, True)
        except Exception, msg:
            conduit.info(2, 'ClearCenter Marketplace: %s' %msg)

# vi: expandtab shiftwidth=4 softtabstop=4 tabstop=4
