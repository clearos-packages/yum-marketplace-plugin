"""ClearCenter Marketplace Repository Plug-in

This is a YUM plug-in which dynamically adds marketplace repositories
"""
import os
import re
import httplib
import urllib
import json
import random
import urlgrabber
import time

from urlparse import urlparse
from yum.plugins import PluginYumExit, TYPE_CORE
from yum.yumRepo import YumRepository as Repository
from yum.parser import varReplace
from xml.etree.ElementTree import parse
from iniparse import INIConfig, BasicConfig

requires_api_version = '2.3'
plugin_type = (TYPE_CORE,)

def touch(filename):
    with open(filename, 'a'):
        os.utime(filename, time.time())

def repo_status(repos, enable=True):
    for repo in sorted(repos):
        ini = INIConfig(open(repo.repofile))
        if enable:
            repo.enable()
            ini[section_id]['enabled'] = 1
        else:
            repo.disable()
            ini[section_id]['enabled'] = 0

        fp = file(filename, "w")
        fp.write(str(ini))
        fp.close()

class wcRepo:
    def __init__(self, conduit):
        global osvendor, enable_beta
        global jws_domain, jws_method, jws_nodes, jws_prefix
        global jws_realm, jws_request, jws_version

        self.conf = conduit.getConf()
        self.yum_repos = conduit.getRepos()

        self.basearch = conduit._base.arch.basearch

        if os.getenv('ENABLE_BETA') != None:
            self.enable_beta = os.getenv('ENABLE_BETA')
        else:
            self.enable_beta = enable_beta

        try:
            fh = open('/etc/product', 'r')
            product = BasicConfig()
            product._readfp(fh)
            fh.close()
        except:
            product = {}

        if 'jws_domain' in product:
            jws_domain = product['jws_domain']
        if 'jws_method' in product:
            jws_method = product['jws_method']
        if 'jws_nodes' in product:
            jws_nodes = int(product['jws_nodes'])
        if 'jws_prefix' in product:
            jws_prefix = product['jws_prefix']
        if 'jws_realm' in product:
            jws_realm = product['jws_realm']
        if 'jws_request' in product:
            jws_request = product['jws_request']
        if 'jws_version' in product:
            jws_version = product['jws_version']
        if 'vendor' in product:
            osvendor = product['vendor']

        random.seed()
        self.url = "%s%d.%s" % (jws_prefix, random.randint(1, jws_nodes), jws_domain)
        self.request = "/%s/%s/%s" % (jws_realm, jws_version, jws_request)

        self.osname = None
        self.software_id = 0
        self.osversion = None
        self.hostkey = None

        if 'name' in product:
            self.osname = product['name']
        if 'software_id' in product:
            software_id = product['software_id']
        if 'version' in product:
            self.osversion = product['version']

        if self.osversion == None:
            fh = open('/etc/clearos-release', 'r')
            line = fh.readline()
            fh.close()
            rx = re.compile(r'release\s+([\d\.]+)')
            match = rx.search(line)
            if match != None:
                self.osversion = match.group(1)

        organization_vendor = { 'clearcenter.com': 'clear' }

        suva_conf = parse(urllib.urlopen('file:///etc/suvad.conf')).getroot()
        for org in suva_conf.findall('organization'):
            if not organization_vendor.has_key(org.attrib.get('name')):
                continue
            if organization_vendor[org.attrib.get('name')] != osvendor:
                continue
            self.hostkey = org.findtext('hostkey')
            break

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

        if self.osversion == None:
            raise Exception('OS version not found.')

        if self.hostkey == None or self.hostkey == '00000000000000000000000000000000':
            raise Exception('system hostkey not found.')

        params = {
            'method': jws_method, 'hostkey': self.hostkey,
            'vendor': osvendor, 'osname': self.osname, 'osversion': self.osversion,
            'arch': self.basearch, 'enablebeta': str(self.enable_beta),
            'software_id': self.software_id
        }

        request = "%s?%s" % (self.request, urllib.urlencode(params))

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
                raise Exception('request failed, error code: %d' % (response['code']))
            else:
                raise Exception('%s Code: %d' % (response['errmsg'], response['code']))

        if response.has_key('community') and response['community'] == 1:
            if not os.path.exists('/var/clearos/registration/verified'):
                repos_to_enable = self.yum_repos.findRepos(
                    'clearos-centos,clearos-centos-updates,clearos-epel,clearos-updates',
                    name_match=True, ignore_case=True)
                repo_status(repos_to_enable, enable=True)
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
                        url = "%s://%s:%s@%s:%s%s" % (
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
                    headers['hostid'] = self.hostkey

                pkgkeys = True
                pkg_headers = {}
                for key, value in headers.iteritems():
                    if key in ['hostid', 'expire', 'key']:
                        repo.http_headers['X-%s' % key.upper()] = value
                    elif key in ['everyting', baserepo]:
                        pkgkeys = False
                        repo.http_headers['X-KEY-%s' % key.upper()] = value
                    else:
                        pkg_headers['X-KEY-%s' % key.upper()] = value

                if pkgkeys:
                    repo.http_headers.update(pkg_headers)
                    group = re.sub(r'^clearos-', r'', r['name'])
                    request = '/pkgapi/%s/%s' % (self.osversion[:1], group)

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
    global rm_pkgs, osvendor, enable_beta
    global jws_domain, jws_method, jws_nodes, jws_prefix
    global jws_realm, jws_request, jws_version

    rm_pkgs = []
    osvendor = conduit.confString('main', 'osvendor', default='clear')
    enable_beta = conduit.confBool('main', 'enable_beta', default=False)

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
        conduit.info(2, 'ClearCenter Marketplace: %s' % msg)

def postdownload_hook(conduit):
    global rm_pkgs, wc_repos

    for pkg in conduit.getDownloadPackages():
        if pkg.repo in wc_repos:
            rpmfn = os.path.basename(pkg.remote_path)
            paths = [pkg.repo.pkgdir]
            if hasattr(pkg.repo, '_old_pkgdirs'):
                paths.extend(pkg.repo._old_pkgdirs)
            for path in paths:
                if os.path.exists(path + '/' + rpmfn):
                    rm_pkgs.append(path + '/' + rpmfn)

def close_hook(conduit):
    global rm_pkgs

    for pkg in rm_pkgs:
        try:
            if os.path.exists(pkg):
                os.unlink(pkg)
        except Exception, msg:
            conduit.info(2, 'ClearCenter Marketplace: %s' % msg)

# vi: expandtab shiftwidth=4 softtabstop=4 tabstop=4
