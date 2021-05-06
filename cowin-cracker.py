import os
import time
from datetime import datetime, timedelta
from pprint import pprint

import couchdb
import requests
from fake_useragent import UserAgent
from retrying import retry
from twilio.rest import Client
from dotenv import load_dotenv

# Load the env file
load_dotenv('.env')

# Variables related to Twilio
account_sid = os.getenv('ACCOUNT_SID')
auth_token = os.getenv('AUTH_TOKEN')
client = Client(account_sid, auth_token)

# Variables related to metrics
no_appointment = "No appointments available yet"
no_appointment_count = 0
total_calls_to_api = 0

# Variables related to the fake UserAgent
ua = UserAgent()
headers = {'User-Agent': ua.chrome}

# Variables related to database connectivity, we are using CouchDB to store response coming in from the api
couch = couchdb.Server(os.getenv('COUCH_DB_CONNECTION_STRING'))
db = couch['cowin']


# responsible for getting list of dates
# currently in my case, in mumbai, for age group 18-44
# booking is only possible 1 day before in period of 7:30 PM to 8:05 PM
def get_list_of_dates():
    list_of_dates = []
    for i in range(1, 2):
        current_date = datetime.now() + timedelta(days=i)
        list_of_dates.append(current_date.strftime('%d-%m-%Y'))
    return list_of_dates


# @retry is reponsible to try executing the method after minimum interval of 5 seconds & max interval of 10 seconds
# I've observed sometimes twilio's service through error, that's had to apply the @retry decorator
# Right now the method is responsible for sending SMS, there are basically two types of SMS
# Success message when we find hospital with 18-44 age group & vaccines count greater than 0
# Failure message, but we only send failure message once in 1 hour
@retry(wait_random_min=5000, wait_random_max=10000)
def send_sms(data):
    global no_appointment_count
    if (data == no_appointment):
        no_appointment_count = no_appointment_count + 1
        if (no_appointment_count % 360 != 0):
            print('only sending sms once in one hour')
            return no_appointment
        else:
            print('will send the no appointment message')
    message = client.messages \
        .create(
            body=data,
            from_=os.getenv('TWILIO_MOBILE_NO'),
            to=os.getenv('MY_MOBILE_NO')
        )
    print(message.sid)


while True:

    # Request URL, modify it to suit your need
    # For reference URL's you can refer to the Swagger Documentation, present here https://apisetu.gov.in/public/marketplace/api/cowin
    # here district_id = 395, represents Mumbai, find your's on the CoWin page
    request_url = 'https://cdn-api.co-vin.in/api/v2/appointment/sessions/public/calendarByDistrict?district_id=395&date='

    list_of_dates = get_list_of_dates()
    list_of_url = []
    list_of_response = []

    for i in list_of_dates:
        list_of_url.append(request_url + i)

    for i in list_of_url:
        print('GET: ' + i)
        chrome_headers = ua.chrome
        response = requests.get(i, headers=headers)
        db.save({'timestamp': str(datetime.now()), 'response': response.json()})
        if (response.status_code == 200):
            list_of_response.append(response)

    print(list_of_response)

    # Keep these variables as it is, do not modify it.
    date = ''
    hospital_name = ''
    pincode = ''
    block_name = ''
    found_appointment = False
    available_capacity = 0

    for i in list_of_response:
        json_i = i.json()
        centers = json_i['centers']
        for center in centers:
            sessions = center['sessions']
            for session in sessions:
                print('min_age_limit: ' + str(session['min_age_limit']) +
                      ', available_capacity: ' + str(available_capacity))
                if (session['min_age_limit'] == 18 and session['available_capacity'] > 0):
                    date = session['date']
                    hospital_name = center['name']
                    pincode = center['pincode']
                    block_name = center['block_name']
                    found_appointment = True
                    available_capacity = session['available_capacity']
                    break
            if found_appointment:
                break
        if found_appointment:
            break

    if found_appointment:
        message = 'Appointment available for hospital ' + \
            str(hospital_name) + ' on date ' + \
            str(date) + ' at block ' + block_name + \
            ', capacity ' + available_capacity
        print(message)
        send_sms(message)
        break
    else:
        message = no_appointment
        send_sms(message)
    total_calls_to_api += 1
    print('total calls to api ' + str(total_calls_to_api))
    time.sleep(10)
