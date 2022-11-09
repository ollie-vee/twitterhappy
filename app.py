import requests
import os
import json
import mysql.connector
from nltk.sentiment import SentimentIntensityAnalyzer
from flask import Flask, render_template
app = Flask(__name__)

bearer_token = "AAAAAAAAAAAAAAAAAAAAAHuUiwEAAAAAnJYVevjpJ%2FvJ15LNYL90Cm7AhZ4%3Dja7ZrCXSiAst7Yj0XqOzRuNT2fZdMuWE0zLB3YHl9d4ovKLCYh"

def create_url():
    return "https://api.twitter.com/2/tweets/sample/stream"

def bearer_oauth(r):
    """
    Method required by bearer token authentication.
    """

    r.headers["Authorization"] = f"Bearer {bearer_token}"
    r.headers["User-Agent"] = "v2SampledStreamPython"
    return r

def connect_to_endpoint(url, params,max_count = 1000):
    json_resp =[]
    count =0
    response = requests.request("GET", url, auth=bearer_oauth, stream=True, params=params)
    for response_line in response.iter_lines():
        if response_line:
            try:
                json_response = json.loads(response_line)
                if json_response['data']['text'].startswith('RT @'):
                    continue
                json_resp.append(json_response)
                count = count+1
            except:
                print("(Badly formatted tweet detected, skipping)")
        if count%max_count ==0:
            print(f"collected {count} tweets")
            break

    if response.status_code != 200:
        error_text = "Request returned an error: {} {}".format(response.status_code, response.text)
        print(error_text)
        #raise Exception(error_text)

    return json_resp

def get_params():
    return {"tweet.fields": ["entities"], "user.fields": ["location"], "expansions":"author_id,geo.place_id" 
           , "place.fields" : ['country']
}

def query(query):
    cnx = mysql.connector.connect(user='root', database='employees')
    cursor = cnx.cursor()

params = get_params()
url = create_url()

SIA = SentimentIntensityAnalyzer()

def get_sentiment_from_json():
    try:
        print("Fetching data stream...")
        json_resp = connect_to_endpoint(url, params, 100)
        print("Extracting data...")
        sumPos = 0
        sumNeg = 0
        sumNeu = 0
        total = len(json_resp)
        for result in json_resp:
            content = result['data']['text']
            sumPos += SIA.polarity_scores(content)["pos"]
            sumNeg += SIA.polarity_scores(content)["neg"]
            sumNeu += SIA.polarity_scores(content)["neu"]
        print("Returning sentiments...")
        return sumPos/total,sumNeu/total,sumNeg/total
    except:
        return -1

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/query", methods=['POST', 'GET'])
def result():
    avgPos,avgNeu,avgNeg = get_sentiment_from_json()
    return render_template("query.html", averagePos=avgPos, averageNeu=avgNeu, averageNeg=avgNeg)