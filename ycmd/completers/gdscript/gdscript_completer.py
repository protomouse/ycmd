# coding=utf-8

# Copyright (C) 2017 Martin Häger
#
# This file is part of ycmd.
#
# ycmd is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# ycmd is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with ycmd.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import unicode_literals
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from future import standard_library
standard_library.install_aliases()
from builtins import *  # noqa

from ycmd.utils import PathsToAllParentFolders
from ycmd.responses import BuildCompletionData
from ycmd.completers.completer import Completer
import os, json, md5, requests


def ConfigFolder():
  if os.name == 'nt':
    return os.path.expandvars( '%APPDATA%\\Godot' )
  else:
    return os.path.expanduser( '~/.godot' )


def ProjectRoot( path ):
  for dir in PathsToAllParentFolders( path ):
    if os.path.isfile( os.path.join( dir, 'engine.cfg' ) ):
      return dir


def PosixPath( path ):
  if os.name == 'nt':
    return path.replace( '\\', '/' )
  return path


class Server( object ):

  def __init__( self, key, port ):
    self.key = key
    self.port = port
    self.path = None


class ServerList( object ):

  def __init__( self ):
    self._servers = []


  def Find( self, path ):
    path = os.path.abspath( path )
    server = next( ( s for s in self._servers if s.path and path.startswith( s.path ) ), None )
    if server:
      return server

    root_path = ProjectRoot( path )
    if not root_path:
      raise ValueError( path + ' is not part of a Godot Engine project' )

    root_key = md5.new( PosixPath( root_path ) ).hexdigest()
    for s in self._servers:
      if s.key == root_key:
        s.path = root_path
        return s


  def Refresh( self ):
    with open( os.path.join( ConfigFolder(), '.autocomplete-servers.json' ) ) as f:
      servers = json.load( f )

    self._servers = [ Server( key, port ) for key, port in servers.iteritems() ]


class GDScriptCompleter( Completer ):
  """
  Completer for GDScript (Godot Engine).

  Reference: https://github.com/neikeq/gd-autocomplete-service
  """

  def __init__( self, user_options ):
    super( GDScriptCompleter, self ).__init__( user_options )
    self._servers = ServerList()


  def SupportedFiletypes( self ):
    return [ 'gdscript' ]


  def ComputeCandidatesInner( self, request_data ):
    path = request_data[ 'filepath' ]
    server = self._servers.Find( path )
    if not server:
      self._servers.Refresh()
      server = self._servers.Find( path )
      if not server:
        return []

    try:
      return self._RequestCompletions( server, request_data )
    except:
      self._servers.Refresh()
      server = self._servers.Find( path )
      if server:
        return self._RequestCompletions( server, request_data )


  def _RequestCompletions( self, server, data ):
    path = data[ 'filepath' ]
    url = 'http://localhost:' + str( server.port )
    req_body = {
      'path': 'res://' + PosixPath( os.path.relpath( path, server.path ) ),
      'text': data[ 'file_data' ][ path ][ 'contents' ],
      'cursor': {
        'row': data[ 'line_num' ] - 1,
        'column': data[ 'column_codepoint' ] - 1
      }
    }
    res = requests.post( url, json = req_body )
    res.raise_for_status()
    res_body = res.json()

    hint = res_body[ 'hint' ].replace( '\n', '' )
    return [ BuildCompletionData( s, detailed_info = hint ) for s in res_body[ 'suggestions' ] ]
