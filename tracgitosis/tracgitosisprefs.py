"""
tracgitosis:
a plugin for Trac, interface for some gitosis-admin configuration
http://trac.edgewall.org
"""

from trac.core import *

from trac.prefs.api import IPreferencePanelProvider
from trac.web.chrome import ITemplateProvider, add_notice, add_warning
from trac.util.translation import _
from trac.config import Option

from subprocess import Popen, PIPE
import os

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

        status, message = self.init_admin(req)
        data = {}
        if status != 0:
          message = 'return code: '+str(status)+'\nmessage:\n'+message
          add_warning(req, _(message))
        sshkey = self.getsshkey(req, req.session.sid)
        data['username'] = req.session.sid
        data['sshkey'] = sshkey
        return 'prefs_tracgitosis.html', data

    def get_templates_dirs(self):
        from pkg_resources import resource_filename
        return [resource_filename(__name__, 'templates')]

    def init_admin(self, req):
        """ Initialisation du dépôt d'admin.

        """
        # on initialise le dépôt git s'il n'existe pas
        status = 0
        stdout = ''
        stderr = ''
        message = ''
        if not os.path.exists(self.env.path+'/'+self.admrepo):
          self.log.debug('cloning '+self.admrepo+' on '+self.gitosis_server+' with user '+self.gitosis_user)
          cmd = ['git', 'clone', self.gitosis_user+'@'+self.gitosis_server+':'+self.admrepo]
          proc = Popen(cmd, shell=False, stdin=None, stdout=PIPE, stderr=PIPE, cwd=self.env.path)
          stdout, stderr = proc.communicate()
          status = proc.returncode
        if status == 0:
          message = stdout
        else:
          add_warning(req, _('Error while cloning gitosis-admin repository. Please check your settings and/or passphrase free connection to this repository for the user running trac (in most cases, the web server user)'))
          message = stderr
        return status, message

    def getsshkey(self, req, username):
        """ Read current ssh public key.

        This function read the file keydir/<user>.pub in the local gitosis-admin working tree.
        """
        keyfile = self.env.path+'/'+self.admrepo+'/keydir/'+username+'.pub'
        if os.path.exists(keyfile):
            f = open(keyfile, 'r')
            pubkey = f.readline()
            f.close()
        else:
            pubkey = ''
        return pubkey

    def setsshkey(self, req, username, key):
        """ Set ssh public key.

        This function write the file keydir/<user>.pub in the local gitosis-admin working tree
        with the given public key.
        """
        #key = req.args.get('sshkey', '').strip()
        # On vérifie si la clé a bien une syntaxe normale
        import re
        status = 0
        if re.search(r'^ssh-rsa [A-Za-z0-9+/]*=* ', key) == None:
            status = 1
            message = 'malformed key (must begin with \'ssh-rsa \' followed by a BASE64 encoded chain)'
        if status == 0:
            relkeyfile = 'keydir/'+username+'.pub'
            keyfile = self.env.path+'/'+self.admrepo+'/'+relkeyfile
            f = open(keyfile, 'w')
            f.write(key+'\n')
            f.close()
            status, message = self.commitkey(relkeyfile)
        if status == 0:
            add_notice(req, _('Your preferences have been saved.'))
        else:
            add_warning(req, _('Error while saving your preferences. Message: '+message))

    def commitkey(self, file):
        """ Commit and push a file

        """
        stdout = ''
        stderr = ''
        message = ''
        status = 0
        repodir = self.env.path+'/'+self.admrepo
        # On met le dépôt à jour
        cmd = ['git', 'pull']
        proc = Popen(cmd, shell=False, stdin=None, stdout=PIPE, stderr=PIPE, cwd=repodir)
        stdout, stderr = proc.communicate()
        status = proc.returncode
        if status == 0:
          # on fait le commit
          cmd = ['git', 'add', file]
          proc = Popen(cmd, shell=False, stdin=None, stdout=PIPE, stderr=PIPE, cwd=repodir)
          stdout, stderr = proc.communicate()
          status = proc.returncode
          cmd = ['git', 'commit', '-m', 'commited by trac']
          proc = Popen(cmd, shell=False, stdin=None, stdout=PIPE, stderr=PIPE, cwd=repodir)
          stdout, stderr = proc.communicate()
          status = proc.returncode
        if status == 1:
          # On vérifie si le message de commit indique qu'il n'y a rien à faire
          pattern = 'nothing to commit'
          if stdout.find(pattern) >= 0:
            status = 0
        if status == 0:
          # On pousse vers gitosis
          cmd = ['git', 'push']
          proc = Popen(cmd, shell=False, stdin=None, stdout=PIPE, stderr=PIPE, cwd=repodir)
          stdout, stderr = proc.communicate()
          status = proc.returncode
        if status == 0:
          message = stdout
        else:
          message = stderr
        return status, message

