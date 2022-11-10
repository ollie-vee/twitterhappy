## Imports
import requests
import sys
import os
import json
import mysql.connector
from time import sleep
from nltk.sentiment import SentimentIntensityAnalyzer
from nltk.downloader import download
download('vader_lexicon')
from flask import Flask, render_template
from multiprocessing import Process
from datetime import datetime
import calendar
import math

############ CONFIG ############
HOST = "localhost"
bearer_token = "AAAAAAAAAAAAAAAAAAAAAHuUiwEAAAAAnJYVevjpJ%2FvJ15LNYL90Cm7AhZ4%3Dja7ZrCXSiAst7Yj0XqOzRuNT2fZdMuWE0zLB3YHl9d4ovKLCYh"
################################

## Create flask app
app = Flask(__name__)
    

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
    print("Querying on host {}".format(HOST))
    cnx = mysql.connector.connect(host=HOST,user='user', password='password', database='twitterquery')
    cursor = cnx.cursor()
    try:
        cursor.execute(query)
        result = cursor.fetchall()
        cnx.commit()
        cursor.close()
        cnx.close()
        return result
    except Exception as error:
        print(error)

params = get_params()
url = create_url()
requestList = []
SIA = SentimentIntensityAnalyzer()

# Create tables in database, if they don't already exist
#query("CREATE TABLE IF NOT EXISTS checkedcount(id SERIAL PRIMARY KEY NOT NULL, notes VARCHAR(255))")
#query("CREATE TABLE IF NOT EXISTS poscount(date DATETIME, value FLOAT)")
#query("CREATE TABLE IF NOT EXISTS negcount(date DATETIME, value FLOAT)")
query("SELECT * FROM checkcount")

def get_current_epoch():
    t=datetime.now()
    return int(calendar.timegm(t.timetuple()))

def get_effective_count():
    global requestList
    curEpoch = get_current_epoch()
    requestList.append(curEpoch)
    index = 0
    for epoch in requestList:
        if curEpoch-epoch > 40:
            requestList.remove(epoch)
    count = round(23940-23850*math.exp(0.000400826*len(requestList)))
    if count < 5: count = 5
    return count

def get_sentiment_from_json(count):
    try:
        print("Fetching data stream...")
        json_resp = connect_to_endpoint(url, params, count)
        print("Extracting data...")
        sumPos = 0
        sumNeg = 0
        total = len(json_resp)
        for result in json_resp:
            content = result['data']['text']
            sumPos += SIA.polarity_scores(content)["pos"]
            sumNeg += SIA.polarity_scores(content)["neg"]
        print("Starting counter...")
        print("Returning data...")
        if total != 0:
            base = sumPos/total + sumNeg/total
            if base != 0:
                return (sumPos/total)/base,(sumNeg/total)/base
        return 0,0
    except Exception as error:
        print(error)
        return -1

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/query", methods=['POST', 'GET'])
def result():
    count = get_effective_count()
    print("Number of tweets surveyed: " + str(count))
    try:
        avgPos,avgNeg = get_sentiment_from_json(count)
        avgPos = str(round(avgPos*100,2))
        avgNeg = str(round(avgNeg*100,2))
        query("INSERT INTO poscount (date, value) VALUES ('{}', '{}')".format(datetime.now(),float(avgPos)))
        query("INSERT INTO negcount (date, value) VALUES ('{}', '{}')".format(datetime.now(),float(avgNeg)))
        query("INSERT INTO checkedcount (notes) VALUES ('success')")
        query1Res = query("SELECT id FROM checkedcount WHERE id = (SELECT MAX(id) FROM checkedcount);")[0][0]
        query2Res = query("SELECT value FROM poscount WHERE value = (SELECT MAX(value) FROM poscount);")[0][0]
        query3Res = query("SELECT value FROM negcount WHERE value = (SELECT MAX(value) FROM negcount);")[0][0]
        return render_template("query.html", averagePos=avgPos + "%", averageNeg=avgNeg + "%", tweetCount = count, checkCount = query1Res, posMax = query2Res, negMax=query3Res)
    except Exception as error:
        print(error)
        return render_template("query.html", averagePos="50%", averageNeg="50%")