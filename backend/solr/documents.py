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

from backend import Translator
from .doc import SolrDoc, SolrDocKeyword, SolrDocKeywordTypes
from .keywordmodel import SolrHierarchy

from backend.autotagging.data_preprocessing import get_clean_content, lemmatize_keywords

import pysolr

import os
import logging as log
from pathlib import Path
from urlpath import URL
import copy
import json
import re
from datetime import datetime, timedelta
from typing import List, Union, Tuple

# log.basicConfig(level=log.INFO)
# log.basicConfig(level=log.ERROR)


class SolrDocuments:
    """
    Provides functionality to strore / modify and retrive documents
    from Solr
    """

    AVAILABLE_SEARCH_FIELDS = SolrDoc.search_fields()
    AVAILABLE_SORT_FIELDS = SolrDoc.sort_fields()

    def __init__(self, config: dict):
        # we'll modify the original configuration
        _conf = copy.deepcopy(config)

        target_languages = _conf.pop("translator_target_languages")
        self.translator = None
        if target_languages:
            self.translator = Translator(target_languages)

        # build the full url
        self.corename = _conf.pop("corename")
        self.url = URL(_conf["url"]) / self.corename
        _conf["url"] = str(self.url)
        # connection to the solr instance
        self.con = pysolr.Solr(**_conf)

    def add(self, *docs: SolrDoc) -> bool:
        """
        Adds documents to Solr
        """
        extracted_data = self._extract(*docs)
        # print(extracted_data)
        docs = [
            SolrDoc.from_extract(doc, res).as_dict(True)
            for doc, res in zip(docs, extracted_data)
        ]

        self.con.add(docs)

    def _extract(self, *docs: SolrDoc) -> List[dict]:
        """
        Extracts the content / metadata of files
        """
        extracted = []
        for doc in docs:
            metadata, content = get_clean_content(doc.full_path)
            extracted.append({"metadata": metadata, "contents": content})

        return extracted

    def get(self, *docs: str) -> Union[SolrDoc, List[SolrDoc]]:
        docs = [self._get(doc) for doc in docs]
        return docs[0] if len(docs) == 1 else docs

    def _get(self, doc: str) -> SolrDoc:
        special_chars = re.compile(r'(?<!\\)(?P<char>[&|+\-!(){}[\]^"~*?:])')
        doc_formated = special_chars.sub(r'\\\g<char>', doc)

        query = f"id:*{doc_formated}"
        res = self.con.search(query)
        hit = self._get_hit(res, doc)
        if hit is None:
            return None
        return SolrDoc.from_hit(hit)

    def update(self, *docs: SolrDoc):
        for doc in docs:
            doc.update_date()

        self.con.add([doc.as_dict(True) for doc in docs])

    def page(
        self,
        page: int = 0,
        num_per_page: int = 5,
        sort_field: str = "id",
        sort_order: str = "asc",
        search_term: str = "",
        start_date: str = "",
        end_date: str = "",
        keywords_only: bool = False,
    ) -> Tuple[int, List[SolrDoc]]:
        """
        Returns a paginated, sorted search query.

        :param page: The page number
        :param num_per_page: Number of entries per page
        :param sort_field: The field used for sorting (all fields in SolrDoc)
        :param sort_order: asc / desc
        :param search_term: Search term which has to appear in any SolrDoc field
        :param start_date: The begin of the time frame to search in
        :param end_date: The end of the time frame to search in
        :param keywords_only: Whether the search should only occur on the keywords field
        :return: total number of pages, search hits for this page
        """
        if sort_field not in SolrDocuments.AVAILABLE_SORT_FIELDS:
            raise ValueError(f"Sort field '{sort_field}' does not exist")

        search_query = self._build_search_query(
            search_term, start_date, end_date, keywords_only
        )

        offset = page * num_per_page
        res = self.con.search(
            search_query,
            rows=num_per_page,
            start=offset,
            sort=f"{sort_field} {sort_order}",
        )

        total_pages = self._calculate_total_pages(res.hits, num_per_page)

        return total_pages, [SolrDoc.from_hit(hit) for hit in res]

    def _build_search_query(
        self, search_term: str, start_date: str, end_date: str, keywords_only: bool
    ) -> str:
        search_fields = SolrDocuments.AVAILABLE_SEARCH_FIELDS

        if keywords_only:
            search_fields = ["keywords"]

        search_query = "*:*"
        if search_term:
            # search term is a string delimited by spaces split it to search for each
            # word individually
            search_terms = search_term.split()

            # translate each word into our target languages defined in the translator
            # config; search terms now include our src language and our dest languages
            if self.translator is not None:
                search_terms = self.translator.translate(search_terms)

            # build and OR query where we search each field in Solr for each search term
            # n_searches = n_fields * n_search_terms
            search_terms = [search_term.lower() for search_term in search_terms]

            search_query = " OR ".join(
                f"{field}:*{search_term}*"
                for field in search_fields
                for search_term in search_terms
            )

        if start_date and end_date:
            search_query = self._append_time_interval(
                search_query, start_date, end_date
            )
        elif start_date:
            # parse start date
            start_date = datetime.strptime(start_date, "%Y-%m-%dT%H:%M:%SZ")
            # reset the start date (hours, minutes, seconds) = 0
            start_date = start_date - timedelta(
                hours=start_date.hour,
                minutes=start_date.minute,
                seconds=start_date.second,
            )
            end_date = start_date + timedelta(hours=24)

            search_query = self._append_time_interval(
                search_query,
                start_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
                end_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
            )

        return search_query

    def _append_time_interval(
        self, search_query: str, start_date: str, end_date: str
    ) -> str:
        return f"({search_query}) AND creation_date: [ {start_date} TO {end_date} ]"

    def _calculate_total_pages(self, n_hits, num_per_page) -> int:
        total_pages = n_hits // num_per_page
        if n_hits % num_per_page:
            total_pages += 1

        return total_pages

    # query syntax = Solr
    def search(self, query: str, rows: int = 300, **kwargs) -> dict:
        return self.con.search(query, rows=rows, **kwargs)

    def delete(self, *doc_ids: str) -> None:
        self.con.delete(id=doc_ids)

    def __contains__(self, doc: str) -> bool:
        query = f"id:*{doc}"
        res = self.con.search(query)
        hit = self._get_hit(res, doc)
        return hit is not None

    def clear(self):
        self.con.delete(q="*:*")

    def _get_hit(self, res: dict, doc: str) -> dict:
        for hit in res:
            if hit["id"] == doc:
                return hit

        return None

    def wipe_keywords(self):
        """
        wipes keywords from all docs; used for debugging
        """
        res = self.search("*:*")
        docs = [SolrDoc.from_hit(hit) for hit in res]
        for doc in docs:
            doc.keywords = [kw for kw in doc.keywords if kw.type == SolrDocKeywordTypes.META]
            self.update(doc)

    def apply_kwm(self, keywords: dict, *doc_ids: str,) -> None:
        """
        Applies a keyword model on every document in Solr.
        The idea is to search the content in Solr for the lemmatized_keyword if it is found
        the (normal)keyword and its parents are applied.

        :param keywords: dict of keywords and corresponding parents
        :param doc_ids:
        :param job_id
        :return:
        """
        lemmatized_keywords = lemmatize_keywords(keywords)

        id_query = self.build_id_query(doc_ids)

        changed_docs = {}
        for lemmatized_keyword, (keyword, parents) in zip(
            lemmatized_keywords, keywords.items()
        ):
            query = self.build_kwm_query(id_query, lemmatized_keyword)

            res = self.search(query)
            res = [SolrDoc.from_hit(hit) for hit in res]

            for doc in res:
                # check whether the doc was already updated
                if doc.id in changed_docs:
                    doc = changed_docs[doc.id]

                # update keywords
                doc.keywords.add(SolrDocKeyword(keyword, SolrDocKeywordTypes.KWM))
                doc.keywords.update(
                    SolrDocKeyword(parent, SolrDocKeywordTypes.KWM)
                    for parent in parents
                )

                # store for bulk update
                changed_docs[doc.id] = doc

        changed_docs = changed_docs.values()
        self.update(*changed_docs)

    def build_kwm_query(self, id_query: str, keyword: str) -> str:
        keyword_query = f"content:{keyword}"
        return f"{id_query} AND {keyword_query}" if id_query else keyword_query

    def build_id_query(self, doc_ids: Tuple[str]) -> str:
        # create a id specific querry if the kwm should be applied only on specific docs
        id_query = ""
        if doc_ids:
            # ID -> id:"ID"
            doc_ids = [f'id:"{doc_id}"' for doc_id in doc_ids]
            # id:"ID1", id:"ID2" -> id:"ID1" OR id:"ID2"
            id_query = " OR ".join(doc_ids)
            # id:"ID1" OR id:"ID2" -> (id:"ID1" OR id:"ID2")
            id_query = f"({id_query})"

        return id_query


__all__ = ["SolrDocuments"]

