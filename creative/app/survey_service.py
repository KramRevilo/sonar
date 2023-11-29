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

"""Various imports to be used for survey functionalites."""
import datetime
import io
import os
import zipfile
from flask import flash
from flask import render_template
from google.cloud import bigquery
from google.cloud import bigquery_storage
import google.cloud.bigquery.magics
import numpy as np
import pandas as pd
import survey_collection
from forms import BRAND_TRACK
from forms import DEFAULT_CSS
from forms import RESPONSES_AT_END

def get_all():
  return survey_collection.get_all()


def get_doc_by_id(survey_id):
  return survey_collection.get_doc_by_id(survey_id)


def get_by_id(survey_id):
  return survey_collection.get_by_id(survey_id)


def delete_by_id(survey_id):
  return survey_collection.delete_by_id(survey_id)


def create(form):
  doc_ref = survey_collection.create(form.data)
  flash(f'{form.surveyname.data} created as {doc_ref.id}')


def update_by_id(survey_id, form):
  edit_doc = survey_collection.update_by_id(survey_id, form.data)
  flash(f'{form.surveyname.data} updated')


def set_form_data(form, edit_doc):
  edit_doc_dict = edit_doc.to_dict()

  for key, value in edit_doc_dict.items():
    form[key].data = edit_doc.get(key,)


def zip_file(survey_id, survey_dict):
  """File download function."""
  # Make these use temp files in '/tmp/' to work around
  # App Engine read only filesystem

  # Prepare data
  current_datetime = datetime.datetime.now().strftime('%Y%m%d')
  surveyname = survey_dict['surveyname'].replace(' ', '-')
  prefix_filename = current_datetime + '_' + surveyname
  survey_type = survey_dict.get('surveytype', '')
  seg_types = [''] if survey_type == BRAND_TRACK else [
      'default_control', 'default_expose'
  ]

  # In order to make the responsetype backward compatible we need to support
  # surveys defined WITHOUT a responsetype and default them to RESPONSES_AT_END.
  # Check to see if there's a key for answer type 'responsetype' and, if not,
  # then this is an old survey. Insert a key:value pair for RESPONSES_AT_END.
  if 'responsetype' not in survey_dict:
    survey_dict['responsetype'] = RESPONSES_AT_END

  # create zip
  template_zips = write_html_template(survey_id, survey_dict, prefix_filename,
                                      seg_types)
  combined_zip = zip_dir(prefix_filename, template_zips)

  # make data response
  with open(combined_zip.filename, 'rb') as file:
    file_data = io.BytesIO(file.read())

  # clean up tmp files
  delete_tmp_zip_files([combined_zip] + template_zips)

  return os.path.basename(combined_zip.filename), file_data


def zip_dir(filename, template_zips):
  with zipfile.ZipFile('/tmp/' + filename + '.zip', 'w',
                       zipfile.ZIP_DEFLATED) as zipdir:
    for zip in template_zips:
      zipdir.write(zip.filename)
  return zipdir


def write_html_template(survey_id, survey_dict, prefix_filename, seg_types):
  template_zips = []

  for seg_type in seg_types:
    dir_name = '/tmp/' + prefix_filename + '_' + seg_type
    # write html file
    with zipfile.ZipFile(dir_name + '.zip', 'w',
                         zipfile.ZIP_DEFLATED) as zip_write_file:
      zip_write_file.writestr(
          'index.html', get_html_template(survey_id, survey_dict, seg_type))
      template_zips.append(zip_write_file)

  return template_zips


def get_html_template(survey_id, survey_dict, seg_type):
  if 'custom_css' in survey_dict:
    custom_css = survey_dict['custom_css']
  else:
    custom_css = DEFAULT_CSS

  return render_template(
      'creative.html',
      survey=survey_dict,
      survey_id=survey_id,
      show_back_button=False,
      response_type=survey_dict['responsetype'],
      all_question_json=get_question_json(survey_dict),
      seg=seg_type,
      custom_css=custom_css,
      thankyou_text=get_thank_you_text(survey_dict),
      next_text=get_next_text(survey_dict),
      comment_text=get_comment_text(survey_dict))


def delete_tmp_zip_files(zipfiles):
  for zipfile in zipfiles:
    os.remove(zipfile.filename)


def get_all_question_text(survey):
  all_question_text = []
  for i in range(1, 6):
    question_text = survey.get('question' + str(i), '')
    if question_text:
      all_question_text.append(question_text)
  return all_question_text


def get_question_json(survey):
  """Retrieving questions from survey in JSON format."""
  all_question_json = []
  for i in range(1, 6):
    question_text = survey.get('question' + str(i), '')
    options = []
    next_question = {}
    question_type = survey.get('question' + str(i) + 'type')
    answers_order = survey.get('question' + str(i) + 'order')
    if question_text:
      question = {
          'id': i,
          'type': question_type,
          'text': question_text,
          'options': options,
          'answersOrder': answers_order,
          'next_question': next_question
      }
    for j in ['a', 'b', 'c', 'd']:
      answer_text = survey.get('answer' + str(i) + j, '')
      if answer_text:
        answer_id = j.capitalize()
        options.append({'id': answer_id, 'role': 'option', 'text': answer_text})
        next_question[answer_id] = survey.get('answer' + str(i) + j + 'next',
                                              '')
    all_question_json.append(question)
  return all_question_json


def get_brand_lift_results(surveyid):
  table_id = os.environ.get('TABLE_ID')
  query = f"""
        SELECT CreatedAt, Segmentation, Response
        FROM `{table_id}`
        WHERE ID = @survey_id
        AND NOT STARTS_WITH(Response, '1:|')
    """
  df = get_survey_responses(surveyid, query)
  if df['Response'].any():
    responselist = df['Response'].str.split(pat=('|'), expand=True)
  else:
    responselist = pd.DataFrame()
  columns = list(responselist)
  for i in columns:
    responselist[i] = responselist[i].str.slice(start=2)
  df = pd.concat([df, responselist], axis=1)
  df.drop(['CreatedAt', 'Response'], axis=1, inplace=True)
  df.replace(regex='default_', value='', inplace=True)

  output = []
  for i in range(len(df.columns) - 1):
    # aggregate count
    pivot = df.pivot_table(
        index='Segmentation', columns=i, aggfunc=len, fill_value=0)
    # rearrange rows
    pivot = pivot.reindex(['expose', 'control'])
    # convert count to percentages
    pivot = pivot.div(pivot.sum(axis=1), axis=0)

    # compute brand lift
    matrix = pivot.to_numpy()
    lift = []
    for col in matrix.T:
      lift.append((col[0] - col[1]) / col[1])

    # append brand lift to matrix
    matrix = np.vstack([matrix, lift])
    output.append(matrix)
  return output


def get_survey_responses(surveyid, query, client=None):
  """Get data from survey"""
  google.cloud.bigquery.magics.context.use_bqstorage_api = True
  project_id = os.environ.get('PROJECT_ID')
  # table_id = os.environ.get('TABLE_ID')

  if client is None:
    client = bigquery.Client(project=project_id)
  bqstorageclient = bigquery_storage.BigQueryReadClient()
  job_config = bigquery.QueryJobConfig(
      query_parameters=[bigquery.ScalarQueryParameter(
          'survey_id','STRING',surveyid)])
  query_job = client.query(query, job_config=job_config)
  df = query_job.result().to_dataframe(bqstorage_client=bqstorageclient)
  return df


def get_survey_responses_context(surveyid, client=None):
 
  """Get data from survey"""
  google.cloud.bigquery.magics.context.use_bqstorage_api = True
  project_id = os.environ.get('PROJECT_ID')
  table_id = os.environ.get('TABLE_ID')

  if client is None:
    client = bigquery.Client(project=project_id)
  bqstorageclient = bigquery_storage.BigQueryReadClient()
  query = f"""
        SELECT CreatedAt, Segmentation, Response
        FROM `{table_id}`
        WHERE ID = @survey_id
        AND NOT STARTS_WITH(Response, '1:|')
    """
  job_config = bigquery.QueryJobConfig(query_parameters=[
      bigquery.ScalarQueryParameter('survey_id', 'STRING', surveyid),
  ])
  query_job = client.query(query, job_config=job_config)
  df = query_job.result().to_dataframe(bqstorage_client=bqstorageclient)

  return df

def get_all_response_counts():
  google.cloud.bigquery.magics.context.use_bqstorage_api = True
  project_id = os.environ.get('PROJECT_ID')
  table_id = os.environ.get('TABLE_ID')
  client = bigquery.Client(project=project_id)
  bqstorageclient = bigquery_storage.BigQueryReadClient()

  query = f"""
    SELECT
    ID,
    Segmentation,
    EXTRACT(DATE FROM max(CreatedAt)) as max_date,
    DATE_DIFF(CURRENT_DATE(), EXTRACT(DATE FROM max(CreatedAt)), DAY) AS days_since_response,
    count(*) as response_count
    FROM `{table_id}`
    WHERE ID is not null
    GROUP BY 1,2
    ORDER BY 1,2
    """
  query_job = client.query(query)
  df = query_job.result().to_dataframe(bqstorage_client=bqstorageclient)
  return df


def get_response_count_from_survey(survey):
  """Get response count from survey"""
  google.cloud.bigquery.magics.context.use_bqstorage_api = True
  project_id = os.environ.get('PROJECT_ID')
  table_id = os.environ.get('TABLE_ID')

  client = bigquery.Client(project=project_id)
  bqstorageclient = bigquery_storage.BigQueryReadClient()
  survey_id = survey.id
  query = f"""
        SELECT
            Segmentation,
            EXTRACT(DATE FROM max(CreatedAt)) as max_date,
            DATE_DIFF(CURRENT_DATE(), EXTRACT(DATE FROM max(CreatedAt)), DAY) AS days_since_response,
            count(*) as response_count
        FROM `{table_id}`
        WHERE ID = @survey_id
        GROUP BY 1
    """

  job_config = bigquery.QueryJobConfig(query_parameters=[
      bigquery.ScalarQueryParameter('survey_id', 'STRING', survey_id),
  ])
  query_job = client.query(query, job_config=job_config)
  df = query_job.result().to_dataframe(bqstorage_client=bqstorageclient)
  converted_dict = df.to_dict('index')
  return converted_dict

def download_responses(surveyid):
  """Download survey responses in a CSV format file."""
  table_id = os.environ.get('TABLE_ID')
  query = f"""
        SELECT CreatedAt, Segmentation, Response
        FROM `{table_id}`
        WHERE ID = @survey_id
        AND NOT STARTS_WITH(Response, '1:|')
    """
  df = get_survey_responses(surveyid, query)
  output = {'Date': [], 'Control/Expose': [], 'Dimension 2': []}
  outputdf = pd.DataFrame(data=output)
  outputdf['Date'] = df['CreatedAt'].values
  outputdf['Control/Expose'] = df['Segmentation'].values
  if df['Response'].any():
    responselist = df['Response'].str.split(pat=('|'), expand=True)
  else:
    responselist = pd.DataFrame()
  columns = list(responselist)
  for i in columns:
    responselist[i] = responselist[i].str.slice(start=2)
  responselist = responselist.rename(
      columns={
          0: 'Response 1',
          1: 'Response 2',
          2: 'Response 3',
          3: 'Response 4',
          4: 'Response 5'
      })
  responselist = responselist.reset_index(drop=True)
  outputdf = pd.concat([outputdf, responselist], axis=1)
  csv = outputdf.to_csv(index=False)
  return csv

def download_responses_with_context(surveyid):
  """Download survey responses in a CSV format file."""
  # get a dataframe of the survey responses
  table_id = os.environ.get('TABLE_ID')
  query = f"""
        SELECT CreatedAt, Segmentation, Response
        FROM `{table_id}`
        WHERE ID = @survey_id
        AND NOT STARTS_WITH(Response, '1:|')
    """
  df = get_survey_responses(surveyid, query)

  # Set the question texts to default values in case we can't talk to
  # the Firestore DB
  question1 = 'Response 1'
  question2 = 'Response 2'
  question3 = 'Response 3'
  question4 = 'Response 4'
  question5 = 'Response 5'

  # Get the survey document object using the convenience function.
  survey_doc = get_doc_by_id(surveyid)
  # Did we get a good document back?
  if survey_doc.exists:
    # convert the document into a dictionary
    survey_info = survey_doc.to_dict()

    # Set variables for question1-5 to the values from the Firestore DB
    # by walking the dictionary items and looking for well-known named
    # keys that are used for the questions
    for key, value in survey_info.items():
      if key == 'question1':
        question1 = survey_info.get(key)
      elif key == 'question2':
        question2 = survey_info.get(key)
      elif key == 'question3':
        question3 = survey_info.get(key)
      elif key == 'question4':
        question4 = survey_info.get(key)
      elif key == 'question5':
        question5 = survey_info.get(key)

  output = {'Date': [], 'Control/Expose': [], 'Dimension 2': []}
  outputdf = pd.DataFrame(data=output)
  outputdf['Date'] = df['CreatedAt'].values
  outputdf['Control/Expose'] = df['Segmentation'].values
  if df['Response'].any():
    responselist = df['Response'].str.split(pat=('|'), expand=True)
  else:
    responselist = pd.DataFrame()
  columns = list(responselist)
  for i in columns:
    responselist[i] = responselist[i].str.slice(start=2)
  responselist = responselist.rename(
      columns={
          0: question1,
          1: question2,
          2: question3,
          3: question4,
          4: question5
      })
  responselist = responselist.reset_index(drop=True)
  outputdf = pd.concat([outputdf, responselist], axis=1)
  csv = outputdf.to_csv(index=False)
  return csv


#def get_thank_you_text(survey):
#  """Multi-language support input for thank you text."""
#  if survey.get('language') == 'ms':
#    thankyou_text = 'Terima Kasih'
#  elif survey.get('language') == 'zh':
#    thankyou_text = '谢谢'
#  elif survey.get('language') == 'ja':
#    thankyou_text = 'ありがとうございました'
#  elif survey.get('language') == 'ko':
#    thankyou_text = '고맙습니다'
#  elif survey.get('language') == 'fr':
#    thankyou_text = 'Merci'
#  elif survey.get('language') == 'es':
#    thankyou_text = 'Gracias'
#  else:
#    thankyou_text = 'Thank You'
#  return thankyou_text


def get_thank_you_text(survey):
  """Multi-language support input for thank you text."""

  language_codes = {
    'ms': 'Terima Kasih',
    'zh': '谢谢',
    'ja': 'ありがとうございました',
    'ko': '고맙습니다',
    'fr': 'Merci',
    'es': 'Gracias',
    'de': 'Danke',
    'it': 'Grazie',
    'pt': 'Obrigado',
    'ru': 'Спасибо',
    'ar': 'شكرا',
    'hi': 'धन्यवाद',
    'tr': 'Teşekkür ederim',
    'vi': 'Cảm ơn',
    'pl': 'Dziękuję',
    'id': 'Terima kasih',
    'th': 'ขอบคุณ',
    'tl': 'Salamat',
    'nl': 'Dankjewel',
    'da': 'Tak',
    'fi': 'Kiitos',
    'el': 'Ευχαριστώ',
    'he': 'תודה',
    'sv': 'Tack',
    'hu': 'Köszönet',
    'cs': 'Děkuji',
    'no': 'Takk',
    'uk': 'Дякую',
    'fa': 'متشکرم',
    'ur': 'شکریہ',
    'ml': 'നന്ദി',
    'ta': 'நன்றி',
    'te': 'ధన్యవాదాలు',
    'kn': 'ಧನ್ಯವಾದಗಳು',
    'gu': 'ધન્યવાદ',
    'mr': 'धन्यवाद',
    'bn': 'ধন্যবাদ'
  }

  language_code = survey.get('language')
  thankyou_text = language_codes.get(language_code) or 'Thank You'
  return thankyou_text

# def get_next_text(survey):
#   """Multi-language support input for next text."""
#   if survey.get('language') == 'ms':
#     next_text = 'Next'
#   elif survey.get('language') == 'zh':
#     next_text = '下一个'
#   elif survey.get('language') == 'ja':
#     next_text = '次へ'
#   elif survey.get('language') == 'ko':
#     next_text = '다음에'
#   elif survey.get('language') == 'fr':
#     next_text = 'Suivante'
#   elif survey.get('language') == 'es':
#     next_text = 'Próxima'
#   else:
#     next_text = 'Next'
#   return next_text

def get_next_text(survey):
  """Multi-language support input for next text."""

  language_codes = {
    'ms': 'Berikutnya',
    'zh': '下一个',
    'ja': '次へ',
    'ko': '다음에',
    'fr': 'Suivante',
    'es': 'Próxima',
    'de': 'Weiter',
    'it': 'Avanti',
    'pt': 'Próximo',
    'ru': 'Следующий',
    'ar': 'التالي',
    'hi': 'अगला',
    'tr': 'Sonraki',
    'vi': 'Kế tiếp',
    'pl': 'Następny',
    'id': 'Berikutnya',
    'th': 'ถัดไป',
    'tl': 'Susunod',
    'nl': 'Volgende',
    'da': 'Næste',
    'fi': 'Seuraava',
    'el': 'Επόμενο',
    'he': 'הבא',
    'sv': 'Nästa',
    'hu': 'Következő',
    'cs': 'Další',
    'no': 'Neste',
    'uk': 'Наступний',
    'fa': 'بعد',
    'ur': 'اگلے',
    'ml': 'അടുത്തത്',
    'ta': 'அடுத்த',
    'te': 'తర్వాత',
    'kn': 'ಮುಂದಿನ',
    'gu': 'આગળ',
    'mr': 'पुढील',
    'bn': 'পরবর্তী'
  }

  language_code = survey.get('language')
  next_text = language_codes.get(language_code) or 'Next'
  return next_text


# def get_comment_text(survey):
#   """Multi-language support input for comment text."""
#   if survey.get('language') == 'ms':
#     comment_text = 'Pilih semua yang berkenaan'
#   elif survey.get('language') == 'zh':
#     comment_text = '选择所有适用的'
#   elif survey.get('language') == 'ja':
#     comment_text = '当てはまるもの全て選択'
#   elif survey.get('language') == 'ko':
#     comment_text = '적용 가능한 모든 항목을 선택하십시오'
#   elif survey.get('language') == 'fr':
#     comment_text = "Choisissez tout ce qui s'applique"
#   elif survey.get('language') == 'es':
#     comment_text = 'Elige todas las aplicables'
#   else:
#     comment_text = 'Choose all applicable'
#   return comment_text


def get_comment_text(survey):
  """Multi-language support input for comment text."""

  language_codes = {
    'ms': 'Pilih semua yang berkenaan',
    'zh': '选择所有适用的',
    'ja': '当てはまるもの全て選択',
    'ko': '적용 가능한 모든 항목을 선택하십시오',
    'fr': "Choisissez tout ce qui s'applique",
    'es': 'Elige todas las aplicables',
    'de': 'Wählen Sie alle zutreffenden aus.',
    'it': 'Seleziona tutte le opzioni applicabili.',
    'pt': 'Escolha todas as opções aplicáveis.',
    'ru': 'Выберите все подходящие.',
    'ar': 'اختر كل ما ينطبق.',
    'hi': 'सभी लागू विकल्प चुनें.',
    'tr': 'Uygun olan tüm seçenekleri seçin.',
    'vi': 'Chọn tất cả các tùy chọn áp dụng.',
    'pl': 'Wybierz wszystkie odpowiednie opcje.',
    'id': 'Pilih semua opsi yang berlaku.',
    'th': 'เลือกตัวเลือกทั้งหมดที่ใช้ได้',
    'tl': 'Piliin ang lahat ng naaangkop na opsyon.',
    'nl': 'Selecteer alle van toepassing zijnde opties.',
    'da': 'Vælg alle relevante muligheder.',
    'fi': 'Valitse kaikki soveltuvat vaihtoehdot.',
    'el': 'Επιλέξτε όλες τις σχετικές επιλογές.',
    'he': 'בחר את כל האפשרויות הרלוונטיות.',
    'sv': 'Välj alla relevanta alternativ.',
    'hu': 'Válassza ki az összes releváns lehetőséget.',
    'cs': 'Vyberte všechny relevantní možnosti.',
    'no': 'Velg alle relevante alternativer.',
    'uk': 'Виберіть усі відповідні варіанти.',
    'fa': 'همه گزینه های مربوطه را انتخاب کنید.',
    'ur': 'تمام متعلقہ اختیارات کا انتخاب کریں۔',
    'ml': 'എല്ലാ ബാധകമായ ഓപ്ഷനുകളും തിരഞ്ഞെടുക്കുക.',
    'ta': 'அனைத்து பொருத்தமான விருப்பங்களையும் தேர்வு செய்யவும்.',
    'te': 'అన్ని వర్తించే ఎంపికలను ఎంచుకోండి.',
    'kn': 'ಎಲ್ಲಾ ಅನ್ವಯಿಸುವ ಆಯ್ಕೆಗಳನ್ನು ಆರಿಸಿ.',
    'gu': '모든 해당 옵션을 선택하세요.',
    'mr': 'सर्व लागू पर्याय निवडा.',
    'bn': 'সभी প্রযোজ্য বিকল্পগুলি নির্বাচন করুন।'
  }

  language_code = survey.get('language')
  comment_text = language_codes.get(language_code) or 'Choose all applicable'
  return comment_text
