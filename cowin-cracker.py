import os
import time
from datetime import datetime, timedelta
from pprint import pprint

import requests
from retrying import retry
from twilio.rest import Client

account_sid = 'TWILIO_ACCOUNT_SID'
auth_token = 'TWILIO_AUTH_TOKEN'
client = Client(account_sid, auth_token)
no_appointment = "No appointments available yet"
no_appointment_count = 0
total_calls_to_api = 0


def get_list_of_dates():
    list_of_dates = []

    for i in range(0, 8):
        current_date = datetime.now() + timedelta(days=i)
        list_of_dates.append(current_date.strftime('%d-%m-%Y'))

    return list_of_dates


@retry(wait_random_min=5000, wait_random_max=10000)
def send_sms(data):
    global no_appointment_count
    if (data == no_appointment):
        no_appointment_count = no_appointment_count + 1
        if (no_appointment_count % 24 != 0):
            print('only sending sms once in one hour')
            return no_appointment
        else:
            print('will send the no appointment message')

    message = client.messages \
        .create(
            body=data,
            from_='ADD_THE_TWILIO_NUMBER_HERE',
            to='ADD_YOUR_PERSONAL_CELL_NO_HERE'
        )

    print(message.sid)


while True:

    request_url = 'https://cdn-api.co-vin.in/api/v2/appointment/sessions/public/calendarByDistrict?district_id=395&date='

    list_of_dates = get_list_of_dates()
    list_of_url = []
    list_of_response = []

    for i in list_of_dates:
        list_of_url.append(request_url + i)

    for i in list_of_url:
        print('GET: ' + i)
        response = requests.get(i)
        if (response.status_code == 200):
            list_of_response.append(response)

    print(list_of_response)

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
                if (session['min_age_limit'] != 45 and session['available_capacity'] > 0):
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
    time.sleep(150)
