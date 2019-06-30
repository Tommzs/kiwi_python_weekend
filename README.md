# kiwi_python_weekend
This code was written during KIWI Python weekend. Many thanks to all KIWI mentors for awesome experience.

Since it was very fast paced dev it is not complete and should only be used as reference for future projects using similar features.

Slides for the weekend: TODO

# ceske_drahy_trips.py
CLI app allows to get journeys from m.cd.cz by given source, destination and date. It also caches data for 10 minutes into redis db.
- Currently only first ~6 journeys of the day are scraped since there were issues with formating of trips around midnight. For the same reason it might fail for long trips.
- Redis db was provided by kiwi.com and might not work. This part needs to be removed or own redis db need to be provided.

# ceske_drahy_trips_sql.py
Same as ceske_drahy_trips.py however uses persistent postgreSQL db (again provided by kiwi.com).

# cd_api.py
Runs test server for Flask+Jinja2 implementation of web app for user-friendly GUI.
- Same limitations as ceske_drahy_trips.py.

# Others
Contains Dockerfile for easy deployment. Possible to deploy on Heroku.
