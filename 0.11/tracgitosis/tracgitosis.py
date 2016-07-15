# -*- coding:Utf-8 -*-

"""
tracgitosis:
a plugin for Trac, interface for some gitosis-admin configuration
http://trac.edgewall.org
"""

from trac.core import *

from trac.admin.api import IAdminPanelProvider
from trac.prefs.api import IPreferencePanelProvider
from trac.web.chrome import ITemplateProvider, add_notice, add_warning
from trac.util.translation import _
from trac.config import Option, _TRUE_VALUES

from subprocess import Popen, PIPE
import os

from string import replace

import ConfigParser

class TracGitosisPrefs(Component):

    implements(IPreferencePanelProvider, ITemplateProvider)


    admrepo = Option(section='tracgitosis',
                     name='admin_repo',
                     default='gitosis-admin',
                     doc='gitosis-admin repository name')

    gitosis_user = Option(section='tracgitosis',
                          name='user',
                          default='git',
                          doc='gitosis user name')

    gitosis_server = Option(section='tracgitosis',
                            name='server',
                            default='localhost',
                            doc='gitosis server name')

    def get_htdocs_dirs(self):
        return []

    ### methods for IPreferencePanelProvider

    def get_preference_panels(self, req):
        """Return a list of available preference panels.
        
        The items returned by this function must be tuple of the form
        `(panel, label)`.
        """
        return [('sshkey', 'gitosis SSH public key')]

    def render_preference_panel(self, req, panel):
        """Process a request for a preference panel.
        
        This function should return a tuple of the form `(template, data)`,
        where `template` is the name of the template to use and `data` is the
        data to be passed to the template.
        """
        if req.method == 'POST':
            self.setsshkey(req, req.session.sid, req.args.get('sshkey', '').strip())
            req.redirect(req.href.prefs(panel or None))

        status, message = init_admin(self.gitosis_user, self.gitosis_server, self.admrepo, self.env.path)
        data = {}
        if status != 0:
          add_warning(req, _('Error while cloning gitosis-admin repository. Please check your settings and/or passphrase free connection to this repository for the user running trac (in most cases, the web server user)'))
          message = 'return code: '+str(status)+'\nmessage:\n'+message
          if message:
            add_warning(req, _(message))
        sshkey = self.getsshkey(req, req.session.sid)
        data['username'] = req.session.sid
        data['sshkey'] = sshkey
        return 'prefs_tracgitosis.html', data

    def get_templates_dirs(self):
        from pkg_resources import resource_filename
        return [resource_filename(__name__, 'templates')]

    def getsshkey(self, req, username):
        """ Read current ssh public key.

        This function read the file keydir/<user>.pub in the local gitosis-admin working tree.
        """
        self.log.debug('update admin repository')
        result, message = gitpull(self.env.path+'/'+self.admrepo)
        if result != 0:
            add_warning('Admin repository update failed. Message: '+message)
        keyfile = self.env.path+'/'+self.admrepo+'/keydir/'+username+'.pub'
        if os.path.exists(keyfile):
            self.log.debug('get ' + username + ' public key')
            f = open(keyfile, 'r')
            pubkey = f.readline()
            f.close()
        else:
            self.log.debug(username + 'has no public key')
            pubkey = ''
        return pubkey

    def setsshkey(self, req, username, key):
        """ Set ssh public key.

        This function write the file keydir/<user>.pub in the local gitosis-admin working tree
        with the given public key.
        """
        #key = req.args.get('sshkey', '').strip()
        # verify key syntax
        import re
        status = 0
        if re.search(r'^(ssh-(rsa|dss) [A-Za-z0-9+/]*=*|$)', key) == None:
            status = 1
            message = 'malformed key (must begin with \'ssh-rsa \' or \'ssh-dss \' followed by a BASE64 encoded chain)'
        if status == 0:
            # Update gitosis-admin repository
            tracname = self.config.get('project', 'name')
            self.log.debug('update admin repository')
            result, message = gitpull(self.env.path+'/'+self.admrepo)
            if result != 0:
                add_warning('Admin repository update failed. Message: '+message)
            # Save key in the file
            relkeyfile = 'keydir/'+username+'.pub'
            keyfile = self.env.path+'/'+self.admrepo+'/'+relkeyfile
            if len(key) > 0:
                self.log.debug('writing key in ' + keyfile)
                f = open(keyfile, 'w')
                f.write(key+'\n')
                f.close()
                self.log.debug('set ' + username + ' public key')
                status, message = gitcommit(self.env.path+'/'+self.admrepo, relkeyfile, tracname)
            else:
                if os.path.exists(keyfile):
                    self.log.debug('deleting file ' + keyfile)
                    os.unlink(keyfile)
                    status, message = gitcommit(self.env.path+'/'+self.admrepo, relkeyfile, tracname, action='rm')
        if status == 0:
            add_notice(req, _('Your preferences have been saved.'))
        else:
            add_warning(req, _('Error while saving your preferences. Message: '+message))

def _save_config(config, req, log):
    """Try to save the config, and display either a success notice or a
    failure warning.
    """
    try:
        config.save()
        add_notice(req, _('Your changes have been saved.'))
    except Exception, e:
        log.error('Error writing to trac.ini: %s', exception_to_unicode(e))
        add_warning(req, _('Error writing to trac.ini, make sure it is '
                           'writable by the web server. Your changes have '
                           'not been saved.'))

class TracGitosisAdminPanel(Component):
    implements(IAdminPanelProvider, ITemplateProvider)

    def get_templates_dirs(self):
        from pkg_resources import resource_filename
        return [resource_filename(__name__, 'templates')]

    def get_admin_panels(self, req):
        if 'TRAC_ADMIN' in req.perm:
            yield ('tracgitosis', _('Trac Gitosis'), 'adminsettings', _('Admin Settings'))

    def render_admin_panel(self, req, cat, page, path_info):
        req.perm.require('TRAC_ADMIN')
        if req.method == 'POST':
            for option in ('admin_repo', 'user', 'server'):
                self.config.set('tracgitosis', option, req.args.get(option))
            _save_config(self.config, req, self.log)
            req.redirect(req.href.admin(cat, page))
        data = {}
        for option in ('admin_repo', 'user', 'server'):
            data[option] = self.config.get('tracgitosis', option)
        return 'admin_tracgitosis_admin.html', {'admin': data}


class TracGitosisAdminRepoPanel(Component):
    implements(IAdminPanelProvider, ITemplateProvider)
    admrepo = Option(section='tracgitosis',
                     name='admin_repo',
                     default='gitosis-admin',
                     doc='gitosis-admin repository name')


    gitosis_user = Option(section='tracgitosis',
                          name='user',
                          default='git',
                          doc='gitosis user name')

    gitosis_server = Option(section='tracgitosis',
                            name='server',
                            default='localhost',
                            doc='gitosis server name')

    def get_templates_dirs(self):
        from pkg_resources import resource_filename
        return [resource_filename(__name__, 'templates')]

    def get_admin_panels(self, req):
        if 'TRAC_ADMIN' in req.perm:
            yield ('tracgitosis', _('Trac Gitosis'), 'reposettings', _('Repository Settings'))

    def render_admin_panel(self, req, cat, page, path_info):
        req.perm.require('TRAC_ADMIN')

        status, message = init_admin(self.gitosis_user, self.gitosis_server, self.admrepo, self.env.path)
        data = {}
        if status != 0:
          add_warning(req, _('Error while cloning gitosis-admin repository. Please check your settings and/or passphrase free connection to this repository for the user running trac (in most cases, the web server user)'))
          message = 'return code: '+str(status)+'\nmessage:\n'+message
          if message:
            add_warning(req, _(message))
        repo = replace(os.path.basename(self.config.get('trac', 'repository_dir')), '.git', '')
        if req.method == 'POST':
            config = {}
            self.log.debug('description: '+req.args.get('description'))
            for option in ('daemon', 'gitweb', 'description', 'owner'):
                 config[option] = req.args.get(option)
            self.set_config(repo, config)
            req.redirect(req.href.admin(cat, page))
        repo = replace(os.path.basename(self.config.get('trac', 'repository_dir')), '.git', '')
        if repo != '':
            data = self.get_config(repo)
        self.log.debug('data: %s', str(data))
        if not data:
            data = {}
        for option in ('daemon', 'gitweb', 'description', 'owner'):
            if option not in data:
                data[option] = ''
        data['gitweb'] = data['gitweb'] in _TRUE_VALUES
        data['daemon'] = data['daemon'] in _TRUE_VALUES
        return 'admin_tracgitosis_repo.html', {'repo': data}

    def get_config(self, repo):
        self.log.debug('get config for repo: '+repo)
        result, message = gitpull(self.env.path+'/'+self.admrepo)
        if result != 0:
            add_warning('Admin repository update failed. Message: '+message)
        conf = self._read_config(self.env.path+'/'+self.admrepo+'/gitosis.conf')
        self.log.debug('conf: %s', str(conf))
        dictItems = {}
        if conf.has_section('repo '+repo):
            items = conf.items('repo '+repo)
            for item in items:
                dictItems[item[0]] = item[1].decode('utf-8')
        return dictItems

    def set_config(self, repo, config):
        self.log.debug('set config for repo: '+repo)
        self.log.debug('config to set: '+str(config))
        result, message = gitpull(self.env.path+'/'+self.admrepo)
        if result != 0:
            add_warning('Admin repository update failed. Message: '+message)
        conf = self._read_config(self.env.path+'/'+self.admrepo+'/gitosis.conf')
        self.log.debug('conf: %s', str(conf))
        if not conf.has_section('repo '+repo):
            conf.add_section('repo '+repo)
        for item in config:
            if item == 'gitweb' or item == 'daemon':
                if config[item] in _TRUE_VALUES:
                    conf.set('repo '+repo, item, 'yes')
                else:
                    conf.set('repo '+repo, item, 'no')
            else:
                conf.set('repo '+repo, item, config[item].encode('utf-8'))
        self._write_config(self.env.path+'/'+self.admrepo+'/gitosis.conf', conf)
        tracname = self.config.get('project', 'name')
        result, message = gitcommit(self.env.path+'/'+self.admrepo, 'gitosis.conf', tracname)
        if result != 0:
            add_warning('Admin repository commit and push failed. Message: '+message)

    def _read_config(self, file_path):
      # read the configuration file
      gitosisConf = sortedConfigParser()
      self.log.debug('read gitosis config file: '+file_path)
    
      if ((file_path != None) and (file_path != "None")):
        if (os.path.exists(file_path)):
          gitosisConf.read(file_path)
          self.log.debug('gitosisConf: %s', str(gitosisConf))
          return gitosisConf   
      return None

    def _write_config(self, file_path, config):
      self.log.debug('writing gitosis config file: '+file_path)

      self.log.debug('config to set: '+str(config))
    
      if ((file_path != None) and (file_path != "None")):
          fd = open(file_path, 'w')
          if os.path.exists(file_path+'.header'):
            hf = open(file_path+'.header', 'r')
            fd.write(hf.read())
            hf.close()
          config.write(fd)
          fd.close()


# derived class to override write method (sorted output)
class sortedConfigParser(ConfigParser.RawConfigParser):
  def write(self, fp):
    """Write a sorted .ini-format representation of the configuration state."""
    fp.write("[gitosis]\n")
    if self.has_section('gitosis'):
      sortedItems = self._sections['gitosis'].keys()
      sortedItems.sort()
      for item in sortedItems:
        if item != '__name__':
          fp.write("%s = %s\n" % (item, str(self._sections['gitosis'][item]).replace('\n', '\n\t')))
    fp.write("\n")
    sortedSections = self._sections.keys()
    sortedSections.sort()
    for section in sortedSections:
      if section != 'gitosis':
        fp.write("[%s]\n" % section)
        sortedItems = self._sections[section].keys()
        sortedItems.sort()
        for item in sortedItems:
          if item != '__name__':
            fp.write("%s = %s\n" % (item, str(self._sections[section][item]).replace('\n', '\n\t')))
      fp.write("\n")


def init_admin(user, server, repo, path):
    """ Initialize admin repository

    """
    status = 0
    stdout = ''
    stderr = ''
    message = ''
    if not os.path.exists(path+'/'+repo):
      cmd = ['git', 'clone', user+'@'+server+':'+repo]
      proc = Popen(cmd, shell=False, stdin=None, stdout=PIPE, stderr=PIPE, cwd=path)
      stdout, stderr = proc.communicate()
      status = proc.returncode
    if status == 0:
      message = stdout
    else:
      message = stderr
    return status, message

def gitpull(path):
    """ repository update (pull)
    """
    # do a reset in case of an error from the previous execution
    cmd = ['git', 'reset', '--hard']
    proc = Popen(cmd, shell=False, stdin=None, stdout=PIPE, stderr=PIPE, cwd=path)
    stdout, stderr = proc.communicate()
    status = proc.returncode
    if status == 0:
      # Clean repository
      cmd = ['git', 'clean', '-f']
      proc = Popen(cmd, shell=False, stdin=None, stdout=PIPE, stderr=PIPE, cwd=path)
      stdout, stderr = proc.communicate()
      status = proc.returncode
    if status == 0:
      # Update the repository
      cmd = ['git', 'pull']
      proc = Popen(cmd, shell=False, stdin=None, stdout=PIPE, stderr=PIPE, cwd=path)
      stdout, stderr = proc.communicate()
      status = proc.returncode
    return status, 'STDOUT: '+stdout+' STDERR: '+stderr


def gitcommit(repodir, file, tracinstancename='', action='add'):
    """ Commit and push a file

    """
    stdout = ''
    stderr = ''
    message = ''
    status = 0
    # add/remove file
    cmd = ['git', action, file]
    proc = Popen(cmd, shell=False, stdin=None, stdout=PIPE, stderr=PIPE, cwd=repodir)
    stdout, stderr = proc.communicate()
    status = proc.returncode
    # check status
    cmd = ['git', 'status', '--short']
    proc = Popen(cmd, shell=False, stdin=None, stdout=PIPE, stderr=PIPE, cwd=repodir)
    stdout, stderr = proc.communicate()
    status = proc.returncode
    # commit
    if len(stdout) > 0:
        cmd = ['git', 'commit', '-m', 'commited by trac instance: ' + tracinstancename ]
        proc = Popen(cmd, shell=False, stdin=None, stdout=PIPE, stderr=PIPE, cwd=repodir)
        stdout, stderr = proc.communicate()
        status = proc.returncode
        if status == 1:
          # check if something was commited
          pattern = 'nothing to commit'
          if stdout.find(pattern) >= 0:
            status = 0
    if status == 0:
      # push to gitosis
      cmd = ['git', 'push']
      proc = Popen(cmd, shell=False, stdin=None, stdout=PIPE, stderr=PIPE, cwd=repodir)
      stdout, stderr = proc.communicate()
      status = proc.returncode
    if status == 0:
      message += stdout
    else:
      message += stdout
      message += stderr
    return status, message
