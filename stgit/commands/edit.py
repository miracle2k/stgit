"""Patch editing command
"""

__copyright__ = """
Copyright (C) 2007, Catalin Marinas <catalin.marinas@gmail.com>

This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License version 2 as
published by the Free Software Foundation.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program; if not, write to the Free Software
Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307 USA
"""

from optparse import OptionParser, make_option
from email.Utils import formatdate

from stgit.commands.common import *
from stgit.utils import *
from stgit.out import *
from stgit import stack, git


help = 'edit a patch description or diff'
usage = """%prog [options] [<patch>]

Edit the description and author information of the given patch (or the
current patch if no patch name was given). With --diff, also edit the
diff.

The editor is invoked with the following contents:

  Patch short description

  From: A U Thor <author@example.com>
  Date: creation date

  Patch long description

If --diff was specified, the diff appears at the bottom, after a
separator:

  ---

  Diff text

Command-line options can be used to modify specific information
without invoking the editor.

If the patch diff is edited but the patch application fails, the
rejected patch is stored in the .stgit-failed.patch file (and also in
.stgit-edit.{diff,txt}). The edited patch can be replaced with one of
these files using the '--file' and '--diff' options.
"""

options = [make_option('-d', '--diff',
                       help = 'edit the patch diff',
                       action = 'store_true'),
           make_option('-f', '--file',
                       help = 'use FILE instead of invoking the editor'),
           make_option('-O', '--diff-opts',
                       help = 'options to pass to git-diff'),
           make_option('--undo',
                       help = 'revert the commit generated by the last edit',
                       action = 'store_true'),
           make_option('-a', '--annotate', metavar = 'NOTE',
                       help = 'annotate the patch log entry'),
           make_option('-m', '--message',
                       help = 'replace the patch description with MESSAGE'),
           make_option('--author', metavar = '"NAME <EMAIL>"',
                       help = 'replae the author details with "NAME <EMAIL>"'),
           make_option('--authname',
                       help = 'replace the author name with AUTHNAME'),
           make_option('--authemail',
                       help = 'replace the author e-mail with AUTHEMAIL'),
           make_option('--authdate',
                       help = 'replace the author date with AUTHDATE'),
           make_option('--commname',
                       help = 'replace the committer name with COMMNAME'),
           make_option('--commemail',
                       help = 'replace the committer e-mail with COMMEMAIL')
           ] + make_sign_options()

def __update_patch(pname, fname, options):
    """Update the current patch from the given file.
    """
    patch = crt_series.get_patch(pname)

    bottom = patch.get_bottom()
    top = patch.get_top()

    f = open(fname)
    message, author_name, author_email, author_date, diff = parse_patch(f)
    f.close()

    out.start('Updating patch "%s"' % pname)

    if options.diff:
        git.switch(bottom)
        try:
            git.apply_patch(fname)
        except:
            # avoid inconsistent repository state
            git.switch(top)
            raise

    crt_series.refresh_patch(message = message,
                             author_name = author_name,
                             author_email = author_email,
                             author_date = author_date,
                             backup = True, log = 'edit')

    if crt_series.empty_patch(pname):
        out.done('empty patch')
    else:
        out.done()

def __edit_update_patch(pname, options):
    """Edit the given patch interactively.
    """
    patch = crt_series.get_patch(pname)

    if options.diff_opts:
        if not options.diff:
            raise CmdException, '--diff-opts only available with --diff'
        diff_flags = options.diff_opts.split()
    else:
        diff_flags = []

    # generate the file to be edited
    descr = patch.get_description().strip()
    descr_lines = descr.split('\n')
    authdate = patch.get_authdate()

    short_descr = descr_lines[0].rstrip()
    long_descr = reduce(lambda x, y: x + '\n' + y,
                        descr_lines[1:], '').strip()

    tmpl = '%(shortdescr)s\n\n' \
           'From: %(authname)s <%(authemail)s>\n'
    if authdate:
        tmpl += 'Date: %(authdate)s\n'
    tmpl += '\n%(longdescr)s\n'

    tmpl_dict = {
        'shortdescr': short_descr,
        'longdescr': long_descr,
        'authname': patch.get_authname(),
        'authemail': patch.get_authemail(),
        'authdate': patch.get_authdate()
        }

    if options.diff:
        # add the patch diff to the edited file
        bottom = patch.get_bottom()
        top = patch.get_top()

        tmpl += '---\n\n' \
                '%(diffstat)s\n' \
                '%(diff)s'

        tmpl_dict['diffstat'] = git.diffstat(rev1 = bottom, rev2 = top)
        tmpl_dict['diff'] = git.diff(rev1 = bottom, rev2 = top,
                                     diff_flags = diff_flags)

    for key in tmpl_dict:
        # make empty strings if key is not available
        if tmpl_dict[key] is None:
            tmpl_dict[key] = ''

    text = tmpl % tmpl_dict

    if options.diff:
        fname = '.stgit-edit.diff'
    else:
        fname = '.stgit-edit.txt'

    # write the file to be edited
    f = open(fname, 'w+')
    f.write(text)
    f.close()

    # invoke the editor
    call_editor(fname)

    __update_patch(pname, fname, options)

def func(parser, options, args):
    """Edit the given patch or the current one.
    """
    crt_pname = crt_series.get_current()

    if not args:
        pname = crt_pname
        if not pname:
            raise CmdException, 'No patches applied'
    elif len(args) == 1:
        pname = args[0]
        if crt_series.patch_unapplied(pname) or crt_series.patch_hidden(pname):
            raise CmdException, 'Cannot edit unapplied or hidden patches'
        elif not crt_series.patch_applied(pname):
            raise CmdException, 'Unknown patch "%s"' % pname
    else:
        parser.error('incorrect number of arguments')

    check_local_changes()
    check_conflicts()
    check_head_top_equal()

    if pname != crt_pname:
        # Go to the patch to be edited
        applied = crt_series.get_applied()
        between = applied[:applied.index(pname):-1]
        pop_patches(between)

    if options.author:
        options.authname, options.authemail = name_email(options.author)

    if options.undo:
        out.start('Undoing the editing of "%s"' % pname)
        crt_series.undo_refresh()
        out.done()
    elif options.message or options.authname or options.authemail \
             or options.authdate or options.commname or options.commemail \
             or options.sign_str:
        # just refresh the patch with the given information
        out.start('Updating patch "%s"' % pname)
        crt_series.refresh_patch(message = options.message,
                                 author_name = options.authname,
                                 author_email = options.authemail,
                                 author_date = options.authdate,
                                 committer_name = options.commname,
                                 committer_email = options.commemail,
                                 backup = True, sign_str = options.sign_str,
                                 log = 'edit',
                                 notes = options.annotate)
        out.done()
    elif options.file:
        __update_patch(pname, options.file, options)
    else:
        __edit_update_patch(pname, options)

    if pname != crt_pname:
        # Push the patches back
        between.reverse()
        push_patches(between)
