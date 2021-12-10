import requests, json, smtplib, ssl, os
import pandas as pd
from dotenv import find_dotenv, load_dotenv
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

load_dotenv(find_dotenv(".env.txt")) #Loads the password credentials into an environmental variable

def housing_info(): #This function returns a response to get all new house information as a request format
    url = "https://us-real-estate.p.rapidapi.com/v2/for-sale"
    querystring = {"offset":"0","limit":"42","state_code":"OR","city":"Portland","sort":"newest"}
    headers = {
        'x-rapidapi-host': "us-real-estate.p.rapidapi.com",
        'x-rapidapi-key': f"{os.getenv('rapid_api_houses')}"
        }

    response = requests.request("GET", url, headers=headers, params=querystring)
    return response

def housing_information(info): #This function parses through the housing_info function and gets the ID of each house and gets the house information
    response = info.json()
    list_id = [information["property_id"] for information in response["data"]["home_search"]["results"] if type(information["tags"]) == list if "investment_opportunity" not in information["tags"]] #Parses out the "investment_opportunity" lands and just get other types of homes and adds in the ID of each home
    perma_links = {}
    for information in response["data"]["home_search"]["results"]: #Gets the HTML link for each house and attaches the ID as the key and the permalink as the value for later use.
        if type(information["tags"]) == list:
            if "investment_opportunity" not in information["tags"]:
                perma_links[information["property_id"]] = information["permalink"] #Parses out the investment oppotunity lands
    return list_id, perma_links

def tuple_to_dict(tuple_list, empty_dictionary): #This is to turn the json fromat that has a list value into dictionary for later use down below
    empty_dictionary = dict(tuple_list)
    return empty_dictionary

def individual_housing_info(list_id, perma_links):#This function gets the ID that was added to the list in "housing_information" and parses through each ID to get the details of the house
    housing_dictionary = {}
    url = "https://us-real-estate.p.rapidapi.com/v2/property-detail"
    headers = {
    'x-rapidapi-host': "us-real-estate.p.rapidapi.com",
    'x-rapidapi-key': f"{os.getenv('rapid_api_houses')}"
    }
    house_information_dictionary = {}
    for housing_id in list_id:
            empty_dict = {}
            params = {"property_id":f"{housing_id}"} #Parses through the list and puts the ID in here to get a request from the server.
            response = requests.request("GET", url, headers=headers, params=params)
            bedroom_info =[features["text"] for features in response.json()["data"]["property_detail"]["features"]]#This gets the bedroom information that is has a list with dictionary values
            all_tuple = [tuple(info.split(":")) for items in bedroom_info for info in items] #Parses through to form a tuple in the list
            tuple_list = [tuples for tuples in all_tuple if len(tuples)==2] #Some of the tuple doesn't have any value so this goes through and gets the ones with only has a key and a value
            house_bedroom_information = tuple_to_dict(tuple_list, empty_dict) #Turns the tupled list into a dictionary
            if house_bedroom_information["Source Property Type"] == " Multi Family":
                bathrooms_total = house_bedroom_information["Full Bathrooms"]#The multifamily home are listed differently so gets the number of bathrooms
            else:
                bathrooms_total = house_bedroom_information["Total Bathrooms"]#This changes the bathroom total for regular hgomes
            house_information_dictionary[housing_id] = {"estimated_down_payment": "{:,}".format(int(response.json()["data"]["property_detail"]["mortgage"]["estimate"]["down_payment"])), #This is a dictionary that adds information about the homes that I want on the email that will be sent to me. It also adds a comma to any number that has 4 or more digits for certain values.
            "montly_payment":"{:,}".format(int(response.json()["data"]["property_detail"]["mortgage"]["estimate"]["monthly_payment"])),
            "total_payment": "{:,}".format(int(response.json()["data"]["property_detail"]["mortgage"]["estimate"]["total_payment"])),
            "monthly_tax": "{:,}".format(int(response.json()["data"]["property_detail"]["mortgage"]["estimate"]["monthly_property_taxes"])),
            "rate": str(int(response.json()["data"]["property_detail"]["mortgage"]["estimate"]["rate"]))+"%",
            "hoa_fees": "{:,}".format(int(response.json()["data"]["property_detail"]["mortgage"]["estimate"]["hoa_fees"])),
            "Number of Bedrooms": house_bedroom_information["Bedrooms"],
            "Total Bathrooms":bathrooms_total,
            "total Living Space": house_bedroom_information["Total Square Feet Living"],
            "Year Built": house_bedroom_information["Year Built"],
            "Property Type": house_bedroom_information["Source Property Type"],
            "address": response.json()["data"]["property_detail"]["address"]["line"],
            "Zip Code":  response.json()["data"]["property_detail"]["address"]["postal_code"],
            "perma_link": perma_links[housing_id]
            }
    return house_information_dictionary #This returns the required dictionary

def Email_table(house_information_dictionary): #This function gets the dictionary from the previous function puts it into a dataframe from Pandas and emails it as a table
    today = (datetime.now()).strftime("%m/%d/%Y")
    for home_id, home_detail in house_information_dictionary.items(): #This loop goes through the dictionary and anything that is labled as a 'permalink' for the home adds a url to give the full url
        home_details = "https://www.realtor.com/realestateandhomes-detail/" + home_detail["perma_link"]
        home_detail["perma_link"] = home_details
    df =pd.DataFrame.from_dict(house_information_dictionary, orient = "index").reset_index(drop = True) #turns the dictionary into a dataframe
    df = df[['perma_link', 'total_payment', 'estimated_down_payment', 'montly_payment', 'monthly_tax', 'rate', 'hoa_fees', #re-arrange the columns accordingly
       'Number of Bedrooms', 'Total Bathrooms', 'total Living Space',
       'Year Built', 'Property Type', 'address', 'Zip Code']]
    context = ssl.create_default_context()#security feature to login to the mailing system
    smtp_server = "smtp.gmail.com"
    port = 587
    sender_email = os.getenv("my_email_address")
    password = os.getenv("gmail_password")
    receiver_email = os.getenv("receiver_email")
    server = smtplib.SMTP(smtp_server,port) #Gets the SMTP url for google
    server.ehlo() #initiates contact with the server
    server.starttls(context=context) #adds in the security setting and commits to the connection
    msg = MIMEMultipart('alternative') #This is library to turn the data frame into a readable table through emails
    msg["subject"] = f"Housing Information {today}"
    msg["From"] = receiver_email
    server.login(sender_email, password)
    html  = """Subject:\
    <html>
      <head></head>
      <body>
        {0}
      </body>
    </html>
    """.format(df.to_html()) #This portion gets the html and turns the dataframe into a readable html format.
    part1 = MIMEText(html,"html") #puts the dataframe into a HTML email format
    msg.attach(part1) #Attaches the html as a message
    server.sendmail(sender_email, receiver_email, msg.as_string()) #Turns the message into a string and sends the email out.
    server.quit()
