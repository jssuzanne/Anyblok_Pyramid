# This file is a part of the AnyBlok / Pyramid project
#
#    Copyright (C) 2016 Jean-Sebastien SUZANNE <jssuzanne@anybox.fr>
#
# This Source Code Form is subject to the terms of the Mozilla Public License,
# v. 2.0. If a copy of the MPL was not distributed with this file,You can
# obtain one at http://mozilla.org/MPL/2.0/.
from os.path import join
from pyramid.config import Configurator as PConfigurator
from anyblok.blok import BlokManager
from anyblok.config import Configuration
from pkg_resources import iter_entry_points
from sqlalchemy_utils.functions import database_exists
from .common import get_registry_for
from . import get_callable
from logging import getLogger
logger = getLogger(__name__)


class AnyBlokRequest:

    def __init__(self, request):
        self.request = request

    @property
    def registry(self):
        dbname = get_callable('get_db_name')(self.request)
        url = Configuration.get_url(db_name=dbname)
        if database_exists(url):
            return get_registry_for(dbname)
        else:
            return None


class InstalledBlokPredicate:

    def __init__(self, blok_name, config):
        self.blok_name = blok_name

    def text(self):
        return 'instaled blok = %s' % self.blok_name

    phash = text

    def __call__(self, context, request):
        if not request.anyblok:
            return False

        if not request.anyblok.registry:
            return False

        # use this method because she is cached
        return request.anyblok.registry.System.Blok.is_installed(
            self.blok_name)


class Configurator(PConfigurator):
    """Overwrite the Pyramid Configurator"""

    def __init__(self, *args, **kwargs):
        kwargs = self.default_kwargs(**kwargs)
        super(Configurator, self).__init__(*args, **kwargs)

    def default_kwargs(self, **kwargs):
        if 'settings' not in kwargs:
            kwargs['settings'] = self.default_setting()

        return kwargs

    def default_setting(self):
        """Call all the entry point ``anyblok_pyramid.settings`` to update
        the argument setting

        the callable need to have one parametter, it is a dict::

            def settings_callable(setting):
                ...

        We add the entry point by the setup file::

            setup(
                ...,
                entry_points={
                    'anyblok_pyramid.settings': [
                        settings_callable=path:settings_callable,
                        ...
                    ],
                },
                ...,
            )


        """
        settings = {}
        for i in iter_entry_points('anyblok_pyramid.settings'):
            logger.debug('Load settings: %r' % i.name)
            i.load()(settings)

        return settings

    def include_from_entry_point(self):
        """Call all the entry point ``anyblok_pyramid.includeme`` to update
        the pyramid configuration

        the callable need to have one parametter(the instance of
        ``Configurator`` class, self)::

            def config_callable(config):
                config.include(...)

        We add the entry point by the setup file::

            setup(
                ...,
                entry_points={
                    'anyblok_pyramid.includeme': [
                        config_callable=path:config_callable,
                        ...
                    ],
                },
                ...,
            )


        """
        self.add_request_method(AnyBlokRequest, 'anyblok', reify=True)
        self.add_route_predicate('installed_blok', InstalledBlokPredicate)
        self.add_view_predicate('installed_blok', InstalledBlokPredicate)
        for i in iter_entry_points('anyblok_pyramid.includeme'):
            logger.debug('Load includeme: %r' % i.name)
            i.load()(self)

    def load_config_bloks(self):
        for blok_name in BlokManager.ordered_bloks:
            blok = BlokManager.get(blok_name)
            if hasattr(blok, 'anyblok_pyramid_config'):
                logger.debug('Load configuration from: %r' % blok_name)
                blok.anyblok_pyramid_config(self)

        # self.scan()


def pyramid_settings(settings):
    """Add in settings the default value for pyramid configuration

    :param settings: dict of the existing settings
    """
    settings.update({
        'pyramid.reload_templates': Configuration.get(
            'pyramid.reload_templates'),
        'pyramid.reload_assets': Configuration.get('pyramid.reload_assets'),
        'pyramid.debug_notfound': Configuration.get(
            'pyramid.debug_notfound'),
        'pyramid.debug_routematch': Configuration.get(
            'pyramid.debug_routematch'),
        'pyramid.prevent_http_cache': Configuration.get(
            'pyramid.prevent_http_cache'),
        'pyramid.debug_all': Configuration.get('pyramid.debug_all'),
        'pyramid.reload_all': Configuration.get('pyramid.reload_all'),
        'pyramid.default_locale_name': Configuration.get(
            'pyramid.default_locale_name'),
    })


def pyramid_tm(config):
    """Add beaker includeme in pyramid configuration

    :param config: Pyramid configurator instance
    """

    config.include('pyramid_tm')


def static_paths(config):
    """Pyramid includeme, add the static path of the blok

    :param config: Pyramid configurator instance
    """

    for blok, cls in BlokManager.bloks.items():
        if hasattr(cls, 'static_paths'):
            paths = cls.static_paths
            if isinstance(paths, str):
                paths = [paths]
        else:
            paths = ['static']

        blok_path = BlokManager.getPath(blok)

        for p in paths:
            config.add_static_view(join(blok, p), join(blok_path, p))
