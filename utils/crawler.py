import requests
import atoma
from argparse import ArgumentParser
from typing import List
from tqdm.auto import tqdm
import os
from time import sleep
import xml.etree.ElementTree as ET
import json


def crawl_arxiv(categories: List[str], max_results: int, sleep_time: int,
                fetch_size: int, output: str):
    documents = []
    base_url = 'http://export.arxiv.org/api/query?'
    base_oai = 'http://export.arxiv.org/oai2?verb=GetRecord&identifier=oai:arXiv.org:{}&metadataPrefix=arXiv'
    oai_tag = '{http://www.openarchives.org/OAI/2.0/}'
    meta_list = []
    for category in categories:
        print('Looking up papers in {}'.format(category))
        url = "{}search_query=cat:{}&max_results={}&sortBy=lastUpdatedDate&sortOrder=descending".format(
            base_url, category, max_results)
        response = requests.get(url)
        feed = atoma.parse_atom_bytes(response.content)
        entries = feed.entries

        for entry in tqdm(entries):
            entry_link = entry.id_
            entry_index = entry_link.rfind('/')
            entry_id = entry_link[entry_index + 1:]
            version_marker = entry_id.rfind('v')
            entry_id = entry_id[:version_marker]
            oai_url = base_oai.format(entry_id)

            metadata_response = requests.get(oai_url)
            if metadata_response.status_code == 200:
                metadata = metadata_response.text
                root = ET.fromstring(metadata)
                record = root.find('{}GetRecord'.format(oai_tag))
                if record is not None:
                    license_link = find_license(record)
                    if is_cc_license(license_link):
                        setattr(entry, 'license', license_link)
                        meta = download_document(entry, output)
                        documents.append(entry)
                        meta_list.append(meta)
                        if len(documents) >= fetch_size:
                            break

            sleep(sleep_time)

        if len(documents) >= fetch_size:
            print("I found what I was looking for. We can stop searching.")
            break

    with open('{}/meta.json'.format(output), 'w') as fout:
        json.dump(meta_list, fout)

    return documents, meta_list


def is_cc_license(link_url):
    if 'creativecommons' in link_url:
        return True

    return False


def download_document(entry, output):
    entry_link = entry.id_
    entry_index = entry_link.rfind('/')
    entry_id = entry_link[entry_index + 1:]
    links = entry.links
    categories = []
    for category in entry.categories:
        categories.append(category.term)
    for link in links:
        if link.title == 'pdf':
            file = requests.get(link.href)
            with open('{}/{}.pdf'.format(output, entry_id), 'wb') as pdf:
                pdf.write(file.content)
    meta = {
        'id': entry_id,
        'published': entry.published.strftime("%d-%m-%Y::%H:%M:%S"),
        'categories': categories,
        'link': entry.id_,
        'title': entry.title.value,
        'license': entry.license

    }
    sleep(5)
    return meta


def find_license(record):
    open_archives_tag = '{http://www.openarchives.org/OAI/2.0/}'
    arxiv_tag = '{http://arxiv.org/OAI/arXiv/}'
    try:
        record = record.find('{}record'.format(open_archives_tag))
        metadata = record.find('{}metadata'.format(open_archives_tag))
        arxiv = metadata.find('{}arXiv'.format(arxiv_tag))
        license_tag = arxiv.find('{}license'.format(arxiv_tag))
        return license_tag.text

    except:
        return ""


if __name__ == "__main__":
    parser = ArgumentParser(description="Document Finder")
    parser.add_argument("--categories", type=str, default='cs.CR')
    parser.add_argument("--max_results", type=int, default=1000)
    parser.add_argument("--source", type=str, default="arxiv")
    parser.add_argument("--sleep_time", type=int, default=5)
    parser.add_argument("--fetch_size", type=int, default=100)
    parser.add_argument("--document_output", type=str, default="output")
    args = parser.parse_args()

    if not os.path.isdir(args.document_output):
        os.makedirs(args.document_output)

    if args.source == "arxiv":

        documents = crawl_arxiv(categories=args.categories.split(),
                                max_results=args.max_results,
                                sleep_time=max(5, args.sleep_time),
                                fetch_size=args.fetch_size,
                                output=args.document_output)

    else:
        print("Only arxiv is supported as a source at the moment")