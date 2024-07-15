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
"""Description of QuestionForm: Generates a survey name field input and 5 questions and answers for customers to fill out.

It would capture the input of the customers and create a survey based on user
input.
"""
import re
from flask_wtf import FlaskForm
from wtforms import SelectField
from wtforms import StringField
from wtforms import SubmitField
from wtforms import TextAreaField
from wtforms.validators import DataRequired
from wtforms.validators import ValidationError
from wtforms.validators import Length

BRAND_TRACK = 'brand_track'
BRAND_LIFT = 'brand_lift'
ANSWERS_ORDERED = 'ORDERED'
ANSWERS_SHUFFLED = 'SHUFFLED'
RESPONSES_AT_END = "Submit Responses at End of Survey"
RESPONSES_IMMEDIATELY = "Submit Responses after each Question"

# this is the default stylesheet for the custom creative
DEFAULT_CSS = """
body {
    margin: 0;
    display: block;
}
/* The .invisible class is used for hiding the 'Thank You' message that
   is not shown until the end of the survey questions.
   It is probably best not to change this class.
*/
.invisible {
    display: none;
}

.master_container {
    border: 1px solid red;
}

/* The #master_container is the box containing all survey elements as a DIV.  
   It contains the survey_container, the thankyou_container, and the bottom
   container - all divs.
*/
#master_container {
    background-color:#008000;
    width: 300px;
    height: 250px;
    border: solid black 1px;
}

/* The #survey_container is the box (div) containing the question
   container and all option_container_[0-4] divs.
*/
#survey_container {
    padding: 7px;
    padding-bottom: 3px;
}

/* .Qbox is the CSS class for controlling the look of the question
   container, including the text of the question itself.
*/
.Qbox {
    font-family: 'Open Sans', sans-serif;
    font-size: 13px;
    padding: 2px 5px;
    height: 45px;
    width: 274px;
    border: 1px solid rgba(255, 255, 255, 0.290196);
    border-radius: 5px;
    color: white;
    text-shadow: rgba(0, 0, 0, 0.8) 1px 1px 1px;
    background-color: rgba(255, 255, 255, 0.14902);
    box-shadow: rgba(0, 0, 0, 0.8) 0px 0px 3px 0px;
    display: table;
}

.Qbox span {
    display: table-cell;
    vertical-align: middle;
}

/* .Abox is the CSS class for controlling the look of the option
   containers (the answers) but does NOT including the formatting
   of the answer/option text: that is in .AText
*/
.Abox {
    border: 1px solid rgba(255, 255, 255, 0.290196);
    border-radius: 5px;
    text-shadow: rgba(0, 0, 0, 0.8) 1px 1px 1px;
    background-color: rgba(255, 255, 255, 0.14902);
    box-shadow: rgba(0, 0, 0, 0.8) 0px 0px 3px 0px;
    position: relative;
    margin: 4px 0;
}

/* The .Abox[selected="true"] class allows for the formmating of
   the answer/option box if the user is using keyboard controls 
   to manually select the answer.
*/
.Abox[selected="true"] {
    background-color: rgba(255, 127, 0, 0.7);
}

/* The .Abox:hover class allows for the formmating of
   the answer/option box when the user hovers their mouse over
   it.
*/
.Abox:hover {
    cursor: pointer;
    background-color: rgba(255, 127, 0, 0.4);
}

/* .AText is used to select the formatting of the answer/option
   text.
*/
.AText {
    font-family: 'Open Sans', sans-serif;
    font-size: 13px;
    color: white;
    text-shadow: rgba(0, 0, 0, 0.8) 1px 1px 1px;
    padding-left: 5px;
    font-size: 12px;
    height: 27px;
    line-height: 27px;
}

/* The #bottom_container class is used to format the blank space
   shown at the bottom of the survey creative.
*/
#bottom_container {
    position: relative;
}

/* The #next_button class is used to format the button that is
   shown at the bottom of a survey question page when that question
   is multiple option as it allows the user to advancce to the next
   question after all their selections are made.
*/
#next_button {
    font-family: 'Open Sans', sans-serif;
    font-size: 13px;
    position: absolute;
    right: 8px;
    top: 0px;
    color: beige;
    padding: 3px 15px;
    text-shadow: rgba(0, 0, 0, 1) 1px 1px 1px;
    background-color: rgba(255, 200, 0, 0.6);
    cursor: pointer;
}

/* The #next_button:hover class is used to format the 'next' button
   when the user hovers over it with their mouse.
*/
#next_button:hover {
    background-color: rgba(255, 127, 80, 0.8);
    color: white;
}

/* Unused */
#question_comment {
    color: #e8e7e7;
    margin: 0 -2px 0 7px;
    font-size: 13px;
}

/* The .thankyoucontainer class allows for formatting of the div
   and its text that is shown at the end of the survey.
*/
.thankyoucontainer {
    height: 100px;
    width: 300px;
    position: absolute;
    top: 100px;
    left: 0px;
    text-align: center;
    font-family: 'Open Sans', sans-serif;
    font-size: 26px;
    color: beige;
    text-shadow: rgba(0, 0, 0, 0.8) 2px 2px 2px
}

body {
    margin:0 auto;
    display:block;
}

/*
add display:none; to make it invisible

If less than 5 answers, it is better to use position: relative; 
With 5 answers position: relative; will push Next button out of the box. 
Use position: absolute; with 5 answers that has multiple options
*/
#ad_background {
    display:none;
    position: absolute;
    background-color: rgba(0, 118, 0, 0.5);
    width: 299px;
}
#ad_text {
    text-align: center;
    color: rgba(0, 98, 0, 0.5);
    font-size: 5px;
}
"""

# LANGUAGE_CHOICES = "'en', 'ms', 'zh', 'ja', 'ko'"

def question_section_is_empty(form, questionNumber):
  """Check if any field of the question input including answer is empty."""
  questionField = 'question' + questionNumber
  answerAField = 'answer' + questionNumber + 'a'
  answerBField = 'answer' + questionNumber + 'b'
  return not (form.data[questionField] and form.data[answerAField] and
              form.data[answerBField] and form.data[answerAField + 'next'] and
              form.data[answerBField + 'next'])


def validate_next_question(form, field):
  """Validate if the question is linked by any other question's answer."""
  questionNumberMatch = re.search('\d', field.name)
  questionNumber = questionNumberMatch.group()
  for questionIndex in range(1, 6):
    for answerChoice in ['a', 'b', 'c', 'd']:
      answerFieldName = 'answer' + str(questionIndex) + answerChoice + 'next'
      answerLinkData = form.data[answerFieldName]
      if answerLinkData == questionNumber and question_section_is_empty(
          form, questionNumber):
        raise ValidationError(
            'Answer ' + answerChoice.upper() + ' from question ' +
            str(questionIndex) +
            ' linked to this question, please fill in this section')

      # is 'end' not really 'end'?
      if answerLinkData.lower() == 'end' and answerLinkData.lower() != 'end':
        raise ValidationError("Syntax for end of survey is 'end' in lowercase, please fix.")


class QuestionForm(FlaskForm):
  """QuestionForm that takes in the survey creation parameters."""

  question1type = SelectField(
      'question1Type', choices=('SINGLE_OPTION', 'MULTIPLE_OPTION'))
  question2type = SelectField(
      'question2Type', choices=('SINGLE_OPTION', 'MULTIPLE_OPTION'))
  question3type = SelectField(
      'question3Type', choices=('SINGLE_OPTION', 'MULTIPLE_OPTION'))
  question4type = SelectField(
      'question4Type', choices=('SINGLE_OPTION', 'MULTIPLE_OPTION'))
  question5type = SelectField(
      'question5Type', choices=('SINGLE_OPTION', 'MULTIPLE_OPTION'))

  # default is 'shuffled'
  question_order_choices = [(ANSWERS_SHUFFLED, 'Shuffled'),
          (ANSWERS_ORDERED, 'Ordered')]

  question1order = SelectField('question1Order', choices=question_order_choices)
  question2order = SelectField('question2Order', choices=question_order_choices)
  question3order = SelectField('question3Order', choices=question_order_choices)
  question4order = SelectField('question4Order', choices=question_order_choices)
  question5order = SelectField('question5Order', choices=question_order_choices)

  language = SelectField('language', choices=('en', 'es', 'fr', 'ms', 'zh', 'ja', 'ko'))

  # make BRAND_TRACK to be the default
  surveytype = SelectField('surveyType', choices=[(
    BRAND_TRACK, 'Brand Track'), (BRAND_LIFT, 'Brand Lift'), ])
    
  surveyname = StringField('surveyName', validators=[DataRequired()])

  # adding responseType as a property of the survey
  responsetype = SelectField('responseType', choices=[
    (RESPONSES_AT_END, 'Submit Responses at End of Survey'),
    (RESPONSES_IMMEDIATELY, 'Submit Responses after each Question')])

  # adding portion of form to customize creative
  custom_css = TextAreaField('custom_css', default=DEFAULT_CSS)

  question1 = StringField('question1', validators=[DataRequired()])
  answer1a = StringField('answer1a', validators=[DataRequired()])
  answer1b = StringField('answer1b', validators=[DataRequired()])
  answer1c = StringField('answer1c')
  answer1d = StringField('answer1d')
  answer1anext = StringField(
      'answer1aNext', default='end', validators=[DataRequired()])
  answer1bnext = StringField(
      'answer1bNext', default='end', validators=[DataRequired()])
  answer1cnext = StringField('answer1cNext', default='end')
  answer1dnext = StringField('answer1dNext', default='end')
  answer2anext = StringField('answer2aNext', default='end')
  answer2bnext = StringField('answer2bNext', default='end')
  answer2cnext = StringField('answer2cNext', default='end')
  answer2dnext = StringField('answer2dNext', default='end')
  answer3anext = StringField('answer3aNext', default='end')
  answer3bnext = StringField('answer3bNext', default='end')
  answer3cnext = StringField('answer3cNext', default='end')
  answer3dnext = StringField('answer3dNext', default='end')
  answer4anext = StringField('answer4aNext', default='end')
  answer4bnext = StringField('answer4bNext', default='end')
  answer4cnext = StringField('answer4cNext', default='end')
  answer4dnext = StringField('answer4dNext', default='end')
  answer5anext = StringField('answer5aNext', default='end')
  answer5bnext = StringField('answer5bNext', default='end')
  answer5cnext = StringField('answer5cNext', default='end')
  answer5dnext = StringField('answer5dNext', default='end')
  question2 = StringField('question2')
  answer2a = StringField('answer2a')
  answer2b = StringField('answer2b')
  answer2c = StringField('answer2c')
  answer2d = StringField('answer2d')
  question3 = StringField('question3')
  answer3a = StringField('answer3a')
  answer3b = StringField('answer3b')
  answer3c = StringField('answer3c')
  answer3d = StringField('answer3d')
  question4 = StringField('question4')
  answer4a = StringField('answer4a')
  answer4b = StringField('answer4b')
  answer4c = StringField('answer4c')
  answer4d = StringField('answer4d')
  question5 = StringField('question5')
  answer5a = StringField('answer5a')
  answer5b = StringField('answer5b')
  answer5c = StringField('answer5c')
  answer5d = StringField('answer5d')
  submit = SubmitField('Submit')

  def validate_question1(form, field):
    validate_next_question(form, field)

  def validate_question2(form, field):
    validate_next_question(form, field)

  def validate_question3(form, field):
    validate_next_question(form, field)

  def validate_question4(form, field):
    validate_next_question(form, field)

  def validate_question5(form, field):
    validate_next_question(form, field)
