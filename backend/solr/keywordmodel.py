# InfiniTag Copyright © 2020 AMOS-5
# Permission is hereby granted,
# free of charge, to any person obtaining a copy of this software and
# associated documentation files (the "Software"), to deal in the Software
# without restriction, including without limitation the rights to use, copy,
# modify, merge, publish, distribute, sublicense, and/or sell copies of the
# Software, and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions: The above copyright notice and this
# permission notice shall be included in all copies or substantial portions
# of the Software. THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY
# KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
# NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
# DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
# OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE
# USE OR OTHER DEALINGS IN THE SOFTWARE.

import pysolr

from typing import List
from urlpath import URL
import copy
import json


class SolrKeyword:
    """
    Class representing an object in the KeywordStorage
    """

    def __init__(self, keyword: str):
        # the name of the field where the keyword is stored
        self.keyword = keyword

    def as_dict(self) -> dict:
        return {"id": self.keyword}

    @staticmethod
    def from_hit(hit: dict) -> str:
        return hit["id"]


class SolrHierarchy:
    def __init__(self, name: str, hierarchy: dict, keywords):
        self.name = name
        self.hierarchy = hierarchy
        self.keywords = keywords

    def as_dict(self) -> dict:
        return {"id": self.name, "hierarchy": json.dumps(self.hierarchy), "keywords": self.keywords}

    def __getitem__(self, k: str):
        return self.hierarchy[k]

    def __setitem__(self, k, v):
        self.hierarchy[k] = v

    def get_keywords(self):
        """
        Extracts all keywords and their paths from the hierarchy
        :return: dict containing keywords as keys and paths as values
        """
        keywords = {}
        to_check = [{'node': root, 'path': []} for root in self.hierarchy]

        #extract all keywords with their parents and put them into a dict
        while len(to_check) != 0:
            cur = to_check.pop()
            path = cur['path'][:]
            if cur['node']['nodeType'] == 'KEYWORD':
                keywords[cur['node']['item']] = path[:]

                if 'children' in cur['node']:
                    path.append(cur['node']['item'])
                    l = [{'node': child, 'path': path} for child in cur['node']['children']]
                    to_check.extend(l)
            else:
                if 'children' in cur['node']:
                    l = [{'node': child, 'path': path} for child in cur['node']['children']]
                    to_check.extend(l)

        return keywords

    @staticmethod
    def from_hit(hit: dict) -> "SolrHierarchy":
        name = hit["id"]
        unicode_hierarchy = SolrHierarchy._unicode(hit["hierarchy"][0])
        hierarchy = json.loads(unicode_hierarchy)
        keywords = []
        if "keywords" in hit:
            keywords = hit["keywords"]
        return SolrHierarchy(name, hierarchy, keywords)

    @staticmethod
    def _unicode(hierarchy: str) -> str:
        """
        Interprets escape characters to apply unicode encoding
        """
        return bytes(hierarchy, "utf-8").decode("unicode_escape")




MAX_ROWS = 5000


class SolrAbstract:
    def __init__(self, config: dict):
        _conf = copy.deepcopy(config)

        # build url for this connection
        corename = _conf.pop("corename")
        _conf["url"] = str(URL(_conf["url"]) / corename)

        self.con = pysolr.Solr(**_conf)

    def delete(self, *ids: str) -> None:
        """
        Deletes items from Solr
        :param ids: Ids to be deleted
        :return:
        """
        self.con.delete(id=ids)

    def clear(self):
        """
        Clears the whole Solr core associated with this object
        """
        self.con.delete(q="*:*")

    def __contains__(self, id_: str) -> bool:
        """
        Checks whether the given id is in the storage
        """
        query = f"id:*{id_}"
        res = self.con.search(query)
        hit = self._get_hit(res, id_)
        return hit is not None

    def _get_hit(self, res: dict, id_: str) -> dict:
        for hit in res:
            if hit["id"] == id_:
                return hit["id"]

        return None


class SolrKeywords(SolrAbstract):
    def __init__(self, config: dict):
        super().__init__(config)

    def add(self, *keywords: str) -> None:
        """
        Adds new keywords to Solr
        :param keywords:
        """
        keywords = [SolrKeyword(keyword).as_dict() for keyword in keywords]
        self.con.add(keywords)

    def get(self) -> List[str]:
        """
        Get every keyword
        :return:
        """

        # search all max results = 5k currently
        result = self.con.search("*:*", rows=MAX_ROWS)
        # extract only the keyword value
        keywords = [SolrKeyword.from_hit(hit) for hit in result]
        return keywords

    def update(self, old: str, new: str) -> None:
        """
        Replaces an existing keyword with a new one (rename)
        :param old:
        :param new:
        :return:
        """
        self.delete(old)
        self.add(new)


class SolrKeywordModel(SolrAbstract):
    """
    Class representing the keyword model as it appears in solr
    """

    def __init__(self, config: dict):
        super().__init__(config)

    def add(self, *hierarchies: SolrHierarchy) -> None:
        """
        Add a hierarchy to the database
        :param hierarchies:
        :return:
        """
        hierarchies = [hierarchy.as_dict() for hierarchy in hierarchies]
        self.con.add(hierarchies)

    def get(self) -> List[SolrHierarchy]:
        """
        Get all keyword models
        :return:
        """
        res = self.con.search("*:*", rows=MAX_ROWS)
        return [SolrHierarchy.from_hit(hit) for hit in res]

    def update(self, *hierarchies: SolrHierarchy) -> None:
        self.add(*hierarchies)


__all__ = [
    "SolrKeywordModel",
    "SolrKeywords",
    "SolrKeyword",
    "SolrAbstract",
    "SolrHierarchy",
]
