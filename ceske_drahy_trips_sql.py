import argparse
from requests_html import HTMLSession
from lxml import html
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from dataclasses_json import dataclass_json
import psycopg2
from psycopg2.extras import RealDictCursor
from slugify import slugify
import json
from copy import deepcopy
import re

sess = HTMLSession()
TABLE_NAME = "journeys"
BASE_URL = "https://m.cd.cz"
pg_config = {
    "host": "pythonweekend.cikhbyfn2gm8.eu-west-1.rds.amazonaws.com",
    "database": "pythonweekend",
    "user": "shareduser",
    "password": "NeverEverSharePasswordsInProductionEnvironement",
}
conn = psycopg2.connect(**pg_config)


@dataclass_json
@dataclass
class Connection:
    source: str
    departure_datetime: str
    destination: str
    arrival_datetime: str
    price: float
    type: str
    carrier: str


def read_args():
    parser = argparse.ArgumentParser(
        description="Generate flight itineraries from input segments."
    )
    parser.add_argument(
        "-s", "--source", required=True, help="place of departure", default=""
    )
    parser.add_argument(
        "-d", "--destination", required=True, help="place of arrival", default=None
    )
    parser.add_argument(
        "-dd", "--departure_date", required=True, help="date of departure", default=None
    )
    args = vars(parser.parse_args())
    return args["source"], args["destination"], args["departure_date"]


def get_response(source, destination, departure_date):
    url = f"{BASE_URL}/spojeni/"
    sess.get(url)
    data = {
        "FROM_0t": source,
        "FROM_0h": "",
        "TO_0t": destination,
        "TO_0h": "",
        "VIA_0h": "",
        "VIA_1h": "",
        "VIA_2h": "",
        "form-time": departure_date.strftime("%H:%M"),
        "form-date": departure_date.strftime("%Y-%m-%d"),
        "deparr": True,
        "cmdSearch": "Hledat",
    }
    req = sess.post("https://m.cd.cz/spojeni/", data=data).html

    return req


def get_price(link):
    # get to eshop
    detail_response = sess.get(f"{BASE_URL}{link}")
    eshop_link = next(
        link for link in detail_response.html.links if link.startswith("/eshop/start")
    )
    # select second class
    response = sess.get(f"{BASE_URL}{eshop_link}")
    form_data = {"DocTypeClass": 2, "DocType": 1, "cmdContinue": "Pokračovat"}
    response = sess.post(response.url, data=form_data)
    # select one-way ticket
    no_return_link = next(
        link for link in response.html.links if link.startswith("/eshop/startnoback")
    )
    response = sess.get(f"{BASE_URL}{no_return_link}")
    # select one regular passenger
    form_data = {
        "psgcount1": 1,
        "psgagecat1": "dospělý (26-64 let)",
        "psgid1": 600,
        "psgcard1": "(žádný)",
        "isBack": "true",
        "cmdContinue": "Pokračovat",
    }
    response = sess.post(response.url, data=form_data)
    return response.html.find(".ticket-desc-price", first=True).text


def parse_response(data, departure_date):
    departure_date = datetime.strptime(departure_date, "%Y-%m-%d")
    results = iter(data.find("a.results"))
    connections = []
    for result in results:
        data = [x.text for i, x in enumerate(result.find("span"))]
        if "" in data:
            data.remove("")  # hotfix to avoid empty element in list
        departure_date_current = deepcopy(departure_date)
        dep_id = 1
        arr_id = 3
        dest_id = 2
        """
        re.findall("(.[0-9]{1,2}:[0-9]{1,2}[A-z].)", data)
        print(data[1])
        
        
        next_day = False
        if len(data) > 7:
            arr_id = 5
            dest_id = 4
        """
        next_day = False
        if len(data[dep_id]) > 5:
            departure_time = datetime.strptime(data[dep_id], "%d.%m. %H:%M").time()
            if not next_day:
                departure_date_current += timedelta(days=1)
                next_day = True
        else:
            departure_time = datetime.strptime(data[dep_id], "%H:%M").time()

        if len(data[arr_id]) > 5:
            arrival_time = datetime.strptime(data[arr_id], "%d.%m. %H:%M").time()
            if not next_day:
                departure_date_current += timedelta(days=1)
                next_day = True
        else:
            arrival_time = datetime.strptime(data[arr_id], "%H:%M").time()

        source = str(data[0]).split(" ", 1)[1]
        destination = str(data[dest_id]).split(" ", 1)[1]
        link = result.attrs["href"]
        price = 0  # get_price(link)
        connections.append(
            Connection(
                source=source,
                departure_datetime=datetime.combine(
                    departure_date_current, departure_time
                ).strftime("%Y-%m-%d, %H:%M:%S"),
                destination=destination,
                arrival_datetime=datetime.combine(
                    departure_date_current, arrival_time
                ).strftime("%Y-%m-%d, %H:%M:%S"),
                price=price,
                type="train",
                carrier="CD",
            )
        )
    return connections


def print_json(connection_list):
    for conn in connection_list:
        if isinstance(conn, Connection):
            print(conn.to_json())
        else:
            print(conn)


def get_response_from_db(source, destination, departure_date):
    sql_select = """
    SELECT 
    * 
    FROM 
    journeys
    WHERE 
    source LIKE %s
    AND
    destination LIKE %s
    AND
    departure_datetime > %s
    AND
    departure_datetime < %s
    """

    curr_time = datetime.strptime(departure_date, "%Y-%m-%d")
    end_time = datetime.strptime(departure_date, "%Y-%m-%d") + timedelta(days=1)

    curr_time = curr_time.strftime("%Y-%m-%d")
    end_time = end_time.strftime("%Y-%m-%d")

    values = [F"{source}%", F"{destination}%", curr_time, end_time]


    with conn.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute(sql_select, values)
        # conn.commit()
        results_dict = cursor.fetchall()
    
        if len(results_dict) > 0:
            return True, results_dict
        else:
            return False, None
    


def cache_connections(source, destination, departure_date, connection_list):
    sql_insert = """
    INSERT INTO journeys (source, destination, departure_datetime, arrival_datetime, carrier,
                          vehicle_type, price, currency)
    VALUES (%(source)s,
            %(destination)s,
		    %(departure_datetime)s,
            %(arrival_datetime)s,
            %(carrier)s,
            %(vehicle_type)s,
            %(price)s,
            %(currency)s);
    """
    for trip in connection_list:
        values = {
            "source": trip["source"],
            "destination": trip["destination"],
            "departure_datetime": trip["departure_datetime"],
            "arrival_datetime": trip["arrival_datetime"],
            "carrier": trip["carrier"],
            "vehicle_type": trip["type"],
            "price": trip["price"],
            "currency": "EUR"
        }
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(sql_insert, values)  # psycopg2 statement execution syntax
            conn.commit()  # important, otherwise your data won’t be inserted!


def get_response_from_website(source, destination, departure_date):
    curr_time = datetime.strptime(departure_date, "%Y-%m-%d")
    end_time = datetime.strptime(departure_date, "%Y-%m-%d") + timedelta(days=1)

    data = get_response(source, destination, curr_time)
    connection_list_json = [
        json.loads(conn.to_json()) for conn in parse_response(data, departure_date)
    ]

    """
    connection_list = []
    while curr_time < end_time:
        data = get_response(source, destination, curr_time)
        connection_list.extend(parse_response(data, departure_date))
        curr_time = datetime.strptime(connection_list[-1].departure_datetime, "%Y-%m-%d, %H:%M:%S") + timedelta(minutes=1)

    connection_list_json = [json.loads(conn.to_json()) for conn in connection_list]
    """
    cache_connections(source, destination, curr_time, connection_list_json)
    return connection_list_json


def get_connection_list(source, destination, departure_date):

    cached, connection_list = get_response_from_db(source, destination, departure_date)
    if not cached:
        print("Using website")
        connection_list = get_response_from_website(source, destination, departure_date)
    else:
        print("Using db")
    return connection_list


if __name__ == "__main__":
    # Read arguments
    source, destination, departure_date = read_args()
    # Get response
    connection_list = get_connection_list(source, destination, departure_date)
    print_json(connection_list)
