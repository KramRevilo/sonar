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
"""Import of required packages/libraries."""

# OS imports
import datetime
import os
import datetime

# Flask imports
from flask import flash
from flask import Flask
from flask import redirect
from flask import render_template
from flask import request
from flask import Response
from flask import send_file
from flask import url_for
from flask_basicauth import BasicAuth
from flask_bootstrap import Bootstrap

# local file imports
import forms
from forms import BRAND_TRACK
from forms import DEFAULT_CSS
import survey_service
from forms import RESPONSES_AT_END
from forms import RESPONSES_IMMEDIATELY

# Project setup
title = 'Sonar'
app = Flask(__name__)
app.config['SECRET_KEY'] = 'supersecretkey'
Bootstrap(app)
app.config['BASIC_AUTH_USERNAME'] = os.environ.get('AUTH_USERNAME')
app.config['BASIC_AUTH_PASSWORD'] = os.environ.get('AUTH_PASSWORD')
basic_auth = BasicAuth(app)
app.config['BASIC_AUTH_FORCE'] = True

# Project constants
ACTIVE_DAYS = 3
ACTIVE_COLOR = '#5cb85c'
ACTIVE_TEXT = 'Active'
WARNING_DAYS = 14
WARNING_COLOR = '#f0ac4f'
WARNING_TEXT = 'Stale'
OLD_DAYS = 14
OLD_COLOR = '#d9534f'
OLD_TEXT = 'Timed Out'
INDETERMINATE_COLOR = '#a0a0a0'
MRC_INIT = 999999999


@app.route('/')
def root():
  return redirect(url_for('index'))


@app.route('/index')
def index():
  all_surveys = survey_service.get_all()
  stat_array = []
  tmp_stats = survey_service.get_all_response_counts()
  
  for survey in all_surveys:
    # filter down to just this survey.id in DataFrame & convert into a dict
    df = tmp_stats.loc[tmp_stats["ID"]==survey.id]
    segmentation_rows = df.to_dict()

    # set high number for last update
    most_recent_change = MRC_INIT

    # build an array with stats for each segmentation
    segs = []
    for x in segmentation_rows['ID']:
        a = {'Segmentation':segmentation_rows['Segmentation'][x],
             'response_count':segmentation_rows['response_count'][x],
             'days_since_response':segmentation_rows['days_since_response'][x] }

        if segmentation_rows['days_since_response'][x] < most_recent_change:
            most_recent_change = segmentation_rows['days_since_response'][x]

        segs.append(a)

    if most_recent_change <= ACTIVE_DAYS:
        color = ACTIVE_COLOR
        status_text = ACTIVE_TEXT
    elif most_recent_change <= WARNING_DAYS:
        color = WARNING_COLOR
        status_text = WARNING_TEXT
    elif most_recent_change > WARNING_DAYS:
        color = OLD_COLOR
        status_text = OLD_TEXT
    else:
        color = INDETERMINATE_COLOR

    if most_recent_change == MRC_INIT:
        most_recent_change = -1

    stat_array.append({'id':survey.id,'stats':segs,'color':color,'last_change':most_recent_change,'status':status_text})

  all_surveys = survey_service.get_all()
  return render_template('index.html', all_surveys=all_surveys, stat_array=stat_array, title=title)


@app.route('/survey/create', methods=['GET', 'POST'])
def create():
  """Survey creation."""
  form = forms.QuestionForm()
  if form.validate_on_submit():
    survey_service.create(form)
    return redirect(url_for('index'))
  return render_template('questions.html', title='Survey Creation', form=form)


@app.route('/survey/preview/<string:survey_id>', methods=['GET'])
def preview(survey_id):
  """Survey preview."""
  survey_doc = survey_service.get_doc_by_id(survey_id)
  if survey_doc.exists:
    survey_info = survey_doc.to_dict()

    if 'custom_css' in survey_info:
        custom_css = survey_info['custom_css']
    else:
        custom_css = DEFAULT_CSS

    if 'responseType' in survey_info:
        response_type = survey_info['surveytype']
    else:
        response_type = RESPONSES_AT_END

    return render_template(
        'creative.html',
        survey=survey_info,
        survey_id=survey_id,
        manual_responses=True,
        show_back_button=True,
        all_question_json=survey_service.get_question_json(survey_info),
        seg='preview',
        custom_css=custom_css,
        response_type = response_type,
        thankyou_text=survey_service.get_thank_you_text(survey_info),
        next_text=survey_service.get_next_text(survey_info),
        comment_text=survey_service.get_comment_text(survey_info))
  else:
    flash('Survey not found')
    return redirect(url_for('index'))


@app.route('/survey/delete', methods=['GET', 'DELETE'])
def delete():
  """Delete survey."""
  if request.method == 'GET':
    docref_id = request.args.get('survey_id')
    survey_service.delete_by_id(docref_id)
    flash(f'Survey \'{docref_id}\' deleted')
  return redirect(url_for('index'))


@app.route('/survey/edit', methods=['POST', 'PUT', 'GET'])
def edit():
  """Edit Survey."""
  # Create form object
  form = forms.QuestionForm()

  # Get info about survey from Firebase
  docref_id = request.args.get('survey_id')
  edit_doc = survey_service.get_doc_by_id(docref_id)

  # Set the form data according to what was loaded from Firebase
  if request.method == 'GET':
    survey_service.set_form_data(form, edit_doc)

  # present page, gather entries upon submission
  if form.validate_on_submit():
    survey_service.update_by_id(docref_id, form)
    return redirect(url_for('index'))
  return render_template('questions.html', form=form)


@app.route('/survey/download_zip/<string:survey_id>', methods=['GET'])
def download_zip(survey_id):
  """Download zip of survey creative(s)."""
  survey_doc = survey_service.get_doc_by_id(survey_id)

  # check the survey to see if it's of the type that needs an alternate creative
  # print(f'in ZIP handler - survey_doc: {survey_doc.to_dict()}')

  # this is the standard survey
  filename, data = survey_service.zip_file(survey_id, survey_doc.to_dict())

  return send_file(
      data,
      mimetype='application/zip',
      etag=False,
      max_age=0,
      last_modified=datetime.datetime.now(),
      as_attachment=True,
      download_name=filename)


@app.route('/survey/download_responses/<string:survey_id>', methods=['GET'])
def download_responses(survey_id):
  """Download survey responses."""
  if request.method == 'GET':
    csv = survey_service.download_responses(survey_id)
    return Response(
        csv,
        mimetype='text/csv',
        headers={'Content-disposition': 'attachment; filename=surveydata.csv'})


@app.route('/survey/download_responses_context/<string:survey_id>', methods=['GET'])
def download_responses_context(survey_id):
  """Download survey responses with context"""
  if request.method == 'GET':
    csv = survey_service.download_responses_with_context(survey_id)
    return Response(
        csv,
        mimetype='text/csv',
        headers={'Content-disposition': 'attachment; filename=surveydata_context.csv'})


@app.route('/survey/reporting/<string:survey_id>', methods=['GET'])
def reporting(survey_id):
  """Survey reporting."""
  survey_doc = survey_service.get_doc_by_id(survey_id)

  if survey_doc.exists:
    survey_info = survey_doc.to_dict()
    results = survey_service.get_brand_lift_results(survey_id)
    return render_template(
        'reporting.html',
        results=results,
        survey=survey_info,
        survey_id=survey_id)
  else:
    flash('Survey not found')
    return redirect(url_for('index'))


@app.context_processor
def inject_receiver_params():
  return {
      'receiver_url': os.environ.get('RECEIVER_URL')
  }


@app.template_filter('get_all_question_text')
def get_all_question_text(survey):
  return survey_service.get_all_question_text(survey.to_dict())


@app.template_filter('format_percentage')
def format_percentage(num):
  return '{:.2%}'.format(num)


@app.template_filter('has_reporting')
def is_brand_track(survey):
  return survey.to_dict().get('surveytype', '') != BRAND_TRACK


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True)
    # index()
