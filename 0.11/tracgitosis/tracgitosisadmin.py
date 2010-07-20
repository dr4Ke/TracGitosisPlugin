# -*- coding: utf-8 -*-

from trac.config import PathOption
from trac.admin.web_ui import *
from trac.util.translation import _

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

#def gitosis_set():

class TracGitosisAdminPanel(Component):
    implements(IAdminPanelProvider)

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
    implements(IAdminPanelProvider)

    def get_admin_panels(self, req):
        if 'TRAC_ADMIN' in req.perm:
            yield ('tracgitosis', _('Trac Gitosis'), 'reposettings', _('Repository Settings'))

    def render_admin_panel(self, req, cat, page, path_info):
        req.perm.require('TRAC_ADMIN')
        #if req.method == 'POST':
        #    for option in ('gitweb', 'description'):
        #        self.config.set('project', option, req.args.get(option))
        #    _save_config(self.config, req, self.log)
        #    req.redirect(req.href.admin(cat, page))
        data = {
            'gitweb': True,
            'description': 'description'
        }
        return 'admin_tracgitosis_repo.html', {'repo': data}

