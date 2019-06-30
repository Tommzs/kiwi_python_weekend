from flask import request, jsonify, Flask, render_template, make_response
import ceske_drahy_trips
from forms import SearchForm

app = Flask(__name__)
app.config["PROPAGATE_EXCEPTIONS"] = True


@app.route("/app/search", methods=["GET", "POST"])
def search_app():
    form = SearchForm(csrf_enabled=False)
    if form.validate_on_submit():
        source = request.form.get("source")  # get data
        destination = request.form.get("destination")
        date = request.form.get("date")
        journeys = ceske_drahy_trips.get_connection_list(source, destination, date)
        template = render_template("search_results.html", journeys=journeys)
        return make_response(template)
    return render_template("search.html", form=form)


if __name__ == "__main__":
    app.run(debug=True)
