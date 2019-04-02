#!/usr/bin/python
# -*- coding: utf-8  -*-
"""
Construct templates and categories for audio files upload from Musikverket.
"""
from collections import OrderedDict
import os.path
from os import listdir

import csv
import pywikibot
import batchupload.common as common
import batchupload.helpers as helpers
from batchupload.make_info import MakeBaseInfo

MAPPINGS_DIR = 'mappings'
IMAGE_DIR = 'audio'
# stem for maintenance categories
BATCH_CAT = 'Media contributed by the Swedish Performing Arts Agency'
BATCH_DATE = '2019-04'  # branch for this particular batch upload
LOGFILE = "audio.log"
PROVIDER = "SMV"


class MusikverketInfo(MakeBaseInfo):

    def __init__(self, **options):
        super(MusikverketInfo, self).__init__(**options)
        self.batch_cat = "{}: {}".format(BATCH_CAT, BATCH_DATE)
        self.commons = pywikibot.Site('commons', 'commons')
        self.wikidata = pywikibot.Site('wikidata', 'wikidata')
        self.log = common.LogFile('', LOGFILE)
        self.photographer_cache = {}
        self.category_cache = []

    def load_data(self, in_file):
        return common.open_and_read_file(in_file, as_json=False)

    def generate_content_cats(self, item):
        item.generate_collection_cat()
        return [x for x in list(item.content_cats) if x is not None]

    def generate_filename(self, item):
        id_no = item.id_no
        if len(item.title) <= 1:
            title = item.description
        else:
            title = item.title
        if item.file_counter > 1:
            id_no = id_no + "_({})".format(item.file_counter)
        return helpers.format_filename(
            title, PROVIDER, id_no)

    def generate_meta_cats(self, item, cats):
        meta_cats = set(item.meta_cats)
        if len(cats) < 1:
            meta_cats.add(
                "{}: needing categorisation".format(BATCH_CAT)
            )
        meta_cats.add(self.batch_cat)
        return list(meta_cats)

    def get_original_filename(self, item):
        orig_filename = None
        file_id_in_item = item.file_id
        path = IMAGE_DIR
        for fname in listdir(path):
            file_on_disc = fname.split(".")[0]
            if file_on_disc == file_id_in_item:
                orig_filename = file_on_disc
        return orig_filename

    def load_mappings(self, update_mappings):
        performers_file = os.path.join(MAPPINGS_DIR, 'performers.json')
        places_file = os.path.join(MAPPINGS_DIR, 'performance_places.json')
        files_file = os.path.join(MAPPINGS_DIR, 'files.json')
        collections_file = os.path.join(MAPPINGS_DIR, 'collections_cats.json')

        if update_mappings:
            print("Updating mappings...")
            print("All mappings are local in this dataset. No updates.")
        else:
            self.mappings['performers'] = common.open_and_read_file(
                performers_file, as_json=True)
            self.mappings['files'] = common.open_and_read_file(
                files_file, as_json=True)
            self.mappings['places'] = common.open_and_read_file(
                places_file, as_json=True)
            self.mappings['collections'] = common.open_and_read_file(
                collections_file, as_json=True)

        pywikibot.output('Loaded all mappings')

    def make_info_template(self, item):
        template_name = 'Musikverket-audio'
        template_data = OrderedDict()
        template_data['title'] = item.generate_title()
        template_data['description'] = item.generate_description()
        template_data['notes'] = item.generate_notes()
        template_data['performance_place'] = item.generate_performance_place()
        template_data['performer'] = item.generate_performers()
        template_data['performance_date'] = item.generate_date()
        template_data['permission'] = item.generate_license()
        template_data['ID'] = item.id_no
        template_data['source'] = item.generate_source()
        return helpers.output_block_template(template_name, template_data, 0)

    def process_data(self, raw_data):
        d = {}
        files_mapping = self.mappings["files"]
        lines_data = raw_data.split("\n")
        records = csv.DictReader(lines_data, delimiter='|')
        tagDict = {'performers': 'XRNAMN',
                   'description': 'XRIHL',
                   'title': 'XRTIT',
                   'format': 'XRIFO',
                   'collection': 'XRSAML',
                   'timestamp': 'XRDATUM',
                   'type': "Typ_av_post",
                   'collection': 'XRSAML',
                   'performance_place': 'XRSPL',
                   'digit_equipment': 'XRDGU',
                   'digit_comments': 'XRDGK',
                   'digit_timestamp': 'XRDGD',
                   'instruments': 'XRSTN',
                   'id_no': 'XRACC'}
        for record in records:
            rec_dic = {}
            for tag in tagDict:
                tag_to_search_for = tagDict.get(tag)
                try:
                    content = record.get(tag_to_search_for).strip()
                    if tag == "description":
                        content = content.replace("<br />", "\n")
                except (AttributeError, IndexError):
                    content = ""
                rec_dic[tag] = content
            id_no = rec_dic["id_no"]

            files_with_this_id = files_mapping.get(id_no)
            file_counter = 0
            for file_id in files_with_this_id:
                file_counter = file_counter + 1
                rec_dic_copy = rec_dic.copy()
                rec_dic_copy["file_id"] = file_id
                rec_dic_copy["file_counter"] = file_counter
                d[file_id] = MusikverketItem(rec_dic_copy, self)
        self.data = d


class MusikverketItem(object):

    def __init__(self, initial_data, musikverket_info):

        for key, value in initial_data.items():
            setattr(self, key, value)

        self.content_cats = set()  # content relevant categories without prefix
        self.meta_cats = set()  # meta/maintenance proto categories
        self.musikverket_info = musikverket_info
        self.commons = pywikibot.Site('commons', 'commons')

    def generate_date(self):
        if self.timestamp:
            return helpers.stdDate(self.timestamp)

    def generate_collection(self):
        library = "Musik- och teaterbiblioteket"
        return "{}, {}".format(library, self.collection)

    def generate_performers(self):
        performers = []
        for person in self.performers.split(";"):
            performers.append(helpers.flip_name(person).strip())
        return "; ".join(performers)

    def generate_performance_place(self):
        if self.performance_place:
            mapping = self.musikverket_info.mappings['places']
            if mapping.get(self.performance_place):
                return "{{Q|" + mapping[self.performance_place] + "}}"
            else:
                return self.performance_place

    def generate_collection_cat(self):
        mapping = self.musikverket_info.mappings['collections']
        if self.collection and mapping.get(self.collection):
            self.content_cats.add(
                mapping.get(self.collection))

    def generate_title(self):
        title = ""
        if self.title:
            title = self.title
        return title

    def generate_description(self):
        desc_string = self.description + "\n"
        swedish = "{{{{sv|{}}}}}".format(desc_string)
        return swedish

    def generate_notes(self):
        notes_string = ""
        if self.instruments:
            instruments = helpers.bolden(
                "Musikinstrument: ") + self.instruments
            notes_string = notes_string + "\n" + instruments + "\n"
        if self.format:
            form = helpers.bolden(
                "Inspelningsformat: ") + self.format
            notes_string = notes_string + "\n" + form + "\n"
        if self.digit_timestamp:
            digit_timestamp = helpers.bolden(
                "Digitaliseringsdatum: ") + self.digit_timestamp
            notes_string = notes_string + "\n" + digit_timestamp + "\n"
        if self.digit_equipment:
            digit_equip = helpers.bolden(
                "Digitaliseringsutrustning: ") + self.digit_equipment
            notes_string = notes_string + "\n" + digit_equip + "\n"
        if self.digit_comments:
            digit_comm = helpers.bolden(
                "Digitaliseringskommentar: ") + self.digit_comments
            notes_string = notes_string + "\n" + digit_comm
        return notes_string

    def generate_source(self):
        template = '{{Musikverket cooperation project}}'
        text = self.type
        if self.collection:
            text = text + " ({})".format(self.collection)
        return "{}\n{}".format(text, template)

    def generate_license(self):
        return "{{PD-old}}"


if __name__ == '__main__':
    MusikverketInfo.main()
