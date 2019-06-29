import argparse
from requests_html import HTMLSession
from lxml import html
from dataclasses import dataclass
from datetime import date, datetime
from dataclasses_json import dataclass_json
from redis import StrictRedis
from slugify import slugify
import json

sess = HTMLSession()
BASE_URL = "https://m.cd.cz"
redis_config = {
  'host': '157.230.124.217',
  'password': 'akd89DSk23Kldl0ram',
  'port': 6379,
}
redis_db = StrictRedis(
            socket_connect_timeout=3,
            **redis_config
            )


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
    data = {"FROM_0t": source,
            "FROM_0h": "",
            "TO_0t": destination,
            "TO_0h": "",
            "VIA_0h": "",
            "VIA_1h": "",
            "VIA_2h": "",
            "form-time": "11:25",
            "form-date": departure_date,
            "deparr": True,
            "cmdSearch": "Hledat"}
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
        data = [
            x.text for i, x in enumerate(result.find("span"))
        ]
        if '' in data:
            data.remove('')  # hotfix to avoid empty element in list
        departure_time = datetime.strptime(data[1], "%H:%M").time()
        source = str(data[0]).split(' ', 1)[1]
        arrival_time = datetime.strptime(data[3], "%H:%M").time()
        destination = str(data[2]).split(' ', 1)[1]
        link = result.attrs["href"]
        price = 0 #get_price(link)
        connections.append(
            Connection(
                source=source,
                departure_datetime=datetime.combine(departure_date, departure_time).strftime("%Y-%m-%d, %H:%M:%S"),
                destination=destination,
                arrival_datetime=datetime.combine(departure_date, arrival_time).strftime("%Y-%m-%d, %H:%M:%S"),
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


def get_response_from_db(key):
    if redis_db.exists(key):
        connection_list = json.loads(redis_db.get(key))
        return True, connection_list
    else:
        return False, None


def cache_connections(key, connection_list):
    redis_db.setex(
        key,
        10*60,
        json.dumps([json.loads(conn.to_json()) for conn in connection_list])
    )
    return redis_db.exists(key)


def get_connection_list(source, destination, departure_date):
    key = "prg_pw:journey:{source}_{destination}_{departure_date}_CD".format(source=slugify(source), destination=slugify(destination), departure_date=departure_date)
    cached, connection_list = get_response_from_db(key)
    if not cached:
        data = get_response(source, destination, departure_date)
        connection_list = parse_response(data, departure_date)
        cached = cache_connections(key, connection_list)
        if not cached:
            print("Warning: Caching of key {key} not sucessfull".format(key=key))
    return connection_list


if __name__ == "__main__":
    # Read arguments
    source, destination, departure_date = read_args()
    # Get response
    connection_list = get_connection_list(source, destination, departure_date)
    print_json(connection_list)
