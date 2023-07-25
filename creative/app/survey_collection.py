# Copyright 2023 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Importing Google Firestore for survey storage."""
from google.cloud import firestore
# from google.cloud import firestore_v1

db = firestore.Client()
# this creates a global containing ALL surveys from the
# firebase datastore
survey_collection = db.collection(u'Surveys')


def get_all():
  return survey_collection.stream()


def get_active():
  global db, survey_collection

  filter_1 = FieldFilter("archived", "!=", True)
  # cannot query by a field when it doesn't exist
  # like in the case of an old Firestore schema being upgraded  :-(
  # filter_2 = FieldFilter("archived", "!=", True)

  # Create the union filter of the two filters (queries)
  #or_filter = Or(filters=[filter_1, filter_2])

  #(db.collection(u"Surveys").where(filter=or_filter).stream())
  return (db.collection(u"Surveys").where(filter=filter_1).stream())


def get_by_id(survey_id):
  global survey_collection

  return survey_collection.document(survey_id)


def get_doc_by_id(survey_id):
  ref = get_by_id(survey_id)
  return ref.get()


def delete_by_id(survey_id):
  global survey_collection

  survey_collection.document(survey_id).delete()


def update_by_id(survey_id, data):
  global db, survey_collection

  ref = survey_collection.document(survey_id)
  ref.update(data)
  return ref


def create(data):
  global survey_collection

  ref = survey_collection.document()
  ref.set(data)
  return ref
