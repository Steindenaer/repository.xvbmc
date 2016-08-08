"""
    SALTS XBMC Addon
    Copyright (C) 2014 tknorris

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
import re
import urllib
import urlparse
import kodi
import log_utils
import dom_parser
from salts_lib import scraper_utils
from salts_lib.constants import FORCE_NO_MATCH
from salts_lib.constants import VIDEO_TYPES
from salts_lib.utils2 import i18n
import scraper

BASE_URL = 'http://scene-rls.com'

class Scraper(scraper.Scraper):
    base_url = BASE_URL

    def __init__(self, timeout=scraper.DEFAULT_TIMEOUT):
        self.timeout = timeout
        self.base_url = kodi.get_setting('%s-base_url' % (self.get_name()))

    @classmethod
    def provides(cls):
        return frozenset([VIDEO_TYPES.MOVIE, VIDEO_TYPES.EPISODE])

    @classmethod
    def get_name(cls):
        return 'scene-rls'

    def get_sources(self, video):
        source_url = self.get_url(video)
        hosters = []
        if source_url and source_url != FORCE_NO_MATCH:
            url = urlparse.urljoin(self.base_url, source_url)
            html = self._http_get(url, require_debrid=True, cache_limit=.5)
            sources = self.__get_post_links(html, video)
            for source in sources:
                if re.search('\.part\.?\d+', source) or '.rar' in source or 'sample' in source or source.endswith('.nfo'): continue
                host = urlparse.urlparse(source).hostname
                quality = sources[source]['quality']
                hoster = {'multi-part': False, 'host': host, 'class': self, 'views': None, 'url': source, 'rating': None, 'quality': quality, 'direct': False}
                if 'format' in sources[source]: hoster['format'] = sources[source]['format']
                hosters.append(hoster)
        return hosters

    def __get_post_links(self, html, video):
        sources = {}
        post = dom_parser.parse_dom(html, 'div', {'class': 'postContent'})
        if post:
            for result in re.finditer('<p\s+style="text-align:\s*center;">(.*?)<br.*?<h2(.*?)(?:<h4|<h3|</div>)', post[0], re.DOTALL):
                release, links = result.groups()
                release = re.sub('</?[^>]*>', '', release)
                release = release.upper()
                is_x265 = 'X265' in release or 'HEVC' in release
                for match in re.finditer('href="([^"]+)', links):
                    stream_url = match.group(1)
                    host = urlparse.urlparse(stream_url).hostname
                    quality = scraper_utils.blog_get_quality(video, release, host)
                    sources[stream_url] = {'quality': quality}
                    if is_x265:
                        sources[stream_url]['format'] = 'x265'
        return sources
        
    def get_url(self, video):
        return self._blog_get_url(video)

    @classmethod
    def get_settings(cls):
        settings = super(cls, cls).get_settings()
        settings = scraper_utils.disable_sub_check(settings)
        name = cls.get_name()
        settings.append('         <setting id="%s-filter" type="slider" range="0,180" option="int" label="     %s" default="30" visible="eq(-4,true)"/>' % (name, i18n('filter_results_days')))
        settings.append('         <setting id="%s-select" type="enum" label="     %s" lvalues="30636|30637" default="0" visible="eq(-5,true)"/>' % (name, i18n('auto_select')))
        return settings

    def search(self, video_type, title, year, season=''):
        search_url = urlparse.urljoin(self.base_url, '/?s=%s&submit=Find')
        search_url = search_url % (urllib.quote_plus(title))
        html = self._http_get(search_url, require_debrid=True, cache_limit=1)
        post_pattern = 'class="postTitle">.*?href="(?P<url>[^"]+)[^>]*>(?P<post_title>[^<]+).*?Published on:\s*(?P<date>[^ ]+ 0*\d+, \d+)'
        date_format = '%b %d, %Y'
        return self._blog_proc_results(html, post_pattern, date_format, video_type, title, year)
