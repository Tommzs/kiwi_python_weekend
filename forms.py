from flask_wtf import FlaskForm
from wtforms import StringField, DateTimeField
from wtforms.validators import DataRequired


class SearchForm(FlaskForm):
    source = StringField("Source", validators=[DataRequired()])
    destination = StringField("Destination", validators=[DataRequired()])
    date = DateTimeField(
        label="Departure date", format="%Y-%m-%d", validators=[DataRequired()]
    )
