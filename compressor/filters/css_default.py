import os
import re
import posixpath

import codecs

from compressor.cache import get_hexdigest, get_hashed_mtime
from compressor.conf import settings
from compressor.filters import FilterBase, FilterError
from compressor.utils import staticfiles

from django.core.files.base import File


URL_PATTERN = re.compile(r'url\(([^\)]+)\)')


class CssAbsoluteFilter(FilterBase):

    def __init__(self, *args, **kwargs):
        super(CssAbsoluteFilter, self).__init__(*args, **kwargs)
        self.root = settings.COMPRESS_ROOT
        self.url = settings.COMPRESS_URL.rstrip('/')
        self.url_path = self.url
        self.has_scheme = False

    def input(self, filename=None, basename=None, **kwargs):
        if filename is not None:
            filename = os.path.normcase(os.path.abspath(filename))
        if (not (filename and filename.startswith(self.root)) and
                not self.find(basename)):
            return self.content
        self.path = basename.replace(os.sep, '/')
        self.path = self.path.lstrip('/')
        if self.url.startswith(('http://', 'https://')):
            self.has_scheme = True
            parts = self.url.split('/')
            self.url = '/'.join(parts[2:])
            self.url_path = '/%s' % '/'.join(parts[3:])
            self.protocol = '%s/' % '/'.join(parts[:2])
            self.host = parts[2]
        self.directory_name = '/'.join((self.url, os.path.dirname(self.path)))
        return URL_PATTERN.sub(self.url_converter, self.content)

    def find(self, basename):
        if settings.DEBUG and basename and staticfiles.finders:
            return staticfiles.finders.find(basename)

    def guess_filename(self, url):
        local_path = url
        if self.has_scheme:
            # COMPRESS_URL had a protocol,
            # remove it and the hostname from our path.
            local_path = local_path.replace(self.protocol + self.host, "", 1)
        # Now, we just need to check if we can find
        # the path from COMPRESS_URL in our url
        if local_path.startswith(self.url_path):
            local_path = local_path.replace(self.url_path, "", 1)
        # Re-build the local full path by adding root
        filename = os.path.join(self.root, local_path.lstrip('/'))
        return os.path.exists(filename) and filename

    def add_suffix(self, url):
        filename = self.guess_filename(url)
        suffix = None
        if filename:
            if settings.COMPRESS_CSS_HASHING_METHOD == "mtime":
                suffix = get_hashed_mtime(filename)
            elif settings.COMPRESS_CSS_HASHING_METHOD == "hash":
                hash_file = open(filename)
                try:
                    suffix = get_hexdigest(hash_file.read(), 12)
                finally:
                    hash_file.close()
            else:
                raise FilterError('COMPRESS_CSS_HASHING_METHOD is configured '
                                  'with an unknown method (%s).')
        if suffix is None:
            return url
        if url.startswith(('http://', 'https://', '/')):
            if "?" in url:
                url = "%s&%s" % (url, suffix)
            else:
                url = "%s?%s" % (url, suffix)
        return url

    def url_converter(self, matchobj):
        from compressor.cache import cache_set
        from compressor.templatetags.versioned_static import StaticCompressorNode
        url = matchobj.group(1)
        url = url.strip(' \'"')
        if url.startswith(('http://', 'https://', '/', 'data:')):
            return "url('%s')" % self.add_suffix(url)
        full_url = posixpath.normpath('/'.join([str(self.directory_name),
                                                url]))
        if settings.COMPRESS_VERSION_CSS_MEDIA:
            name = full_url
            if "/static/" in name:
                name = name[8:]
            if "?" in name:
                name = name[:name.find("?")]
            if "#" in name:
                name = name[:name.find("#")]
            
            # Prepare the compressor
            context = {'name': name}
            forced = False
            node = StaticCompressorNode(name)
            compressor = node.compressor_cls(content=node.name,
                                             context=context)
            
            new_filepath = compressor.get_filepath(node.name)
            source_filename = compressor.get_filename(node.name)
            source_file = codecs.open(source_filename, 'rb')

            # See if it has been rendered offline
            cached_offline = node.render_offline(compressor, forced)
            if cached_offline:
                return cached_offline

            # Check cache
            cache_key, cache_content = node.render_cached(compressor, forced)
            if cache_content is not None:
                return cache_content

            # Save the file, and store it in the cache.
            if not compressor.storage.exists(new_filepath) or forced:
                compressor.storage.save(new_filepath, File(source_file))

            rendered_output = compressor.storage.url(new_filepath)
            if cache_key:
                cache_set(cache_key, rendered_output)

        full_url = rendered_output


        if self.has_scheme:
            full_url = "%s%s" % (self.protocol, full_url)
        return "url('%s')" % self.add_suffix(full_url)
