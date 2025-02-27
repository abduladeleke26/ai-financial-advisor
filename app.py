import time
from openai import OpenAI
from pypdf import PdfReader
from flask import Flask, render_template, request, session, jsonify
import base64
import json
import requests
import datetime
from collections import defaultdict
import os



app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = "your-secret-key"



clientId = os.environ.get('PLAID_CLIENT')
key = os.environ.get('PLAID_KEY')
PLAID_BASE_URL = f"https://production.plaid.com"


t = ""

client = OpenAI(api_key=os.environ.get('AI_KEY'))

banksss =""
categories = None
current = "empty"

bankInstructions = """
youre a financial advisor making a html page inside of <div></div>

TITLE SHOULD BE ON ITS OWN LINE IN <h1></h1>

take the category and the amounts given to you and make a html table.

if the amount starts with "-" it is a withdrawal.


no table should have two of the same categories.
  
every table should have a total (total withdrawals, total deposits)

every table should have a title (withdrawals, deposits) in <h2></h2>

make sure both tables are always separate they cannot touch.

keep deposits and withdrawals separate.

Finally give financial advice. Talk about where the user did good and what needs to be improved.

THE ONLY THING I SHOULD SEE IS THE TITLE, 2 TABLES(WITHDRAWAL AND DEPOSIT), AND THE FINANCIAL ADVICE.

NEVER MENTION ANYTHING ELSE OUTSIDE OF FINANCIAL ADVICE

"""

instructions = """
  youre a financial advisor making a html page inside of <div></div> categorizing every single statement.
  TITLE SHOULD BE ON ITS OWN LINE IN <h1></h1>
  if the amount starts with "-" it is a withdrawal.
  go through each withdrawal and see what category fits the best out of the following:
  Home & Utilities  
  Transportation  
  Groceries
  Personal & Family Care
  Health 
  Insurance
  Restaurants & Dining
  Shopping & Entertainment
  Travel
  Cash, Checks & Misc
  Giving
  Business Expenses
  Education   
  Finance 
  Uncategorized 
  
  go through each deposit and see what category fits the best
  
  
  once everything is categorized sum up each category with the transaction in it and put it on a table in HTML FORMAT.
  
  no table should have two of the same categories.
  
  every table should have a total (total withdrawals, total deposits)
  
  every table should have a title (withdrawals, deposits) in <h2></h2>
  
  make sure both tables are always separate they cannot touch.
  
  keep deposits and withdrawals separate.
  
  Finally give financial advice. Talk about where the user did good and what needs to be improved.
  
  THE ONLY THING I SHOULD SEE IS THE TITLE, TABLES, AND THE FINANCIAL ADVICE.
  
  
  """

def get_transactions(token):
    low = 0
    hi = 0
    high = None
    lowest = None

    start_date = (datetime.datetime.now() - datetime.timedelta(days=30)).strftime("%Y-%m-%d")
    end_date = datetime.datetime.now().strftime("%Y-%m-%d")

    url = f"{PLAID_BASE_URL}/transactions/get"
    payload = {
        "client_id": clientId,
        "secret": key,
        "access_token": token,
        "start_date": start_date,
        "end_date": end_date,
        "options": {"count": 100, "offset": 0}
    }
    time.sleep(10)
    response = requests.post(url, json=payload)
    response = response.json()

    if response.get("error_code"):
        return get_transactions(token)

    response = response.get("transactions")
    if response is None:
        return get_transactions(token)

    



    transactions = []

    category_totals = defaultdict(float)
    for statement in response:





        category = statement.get("personal_finance_category")
        category = category.get("primary")
        category = category.replace("_"," ")
        if not category:
            category = ["Uncategorized"]

        if statement.get("amount", 0) < 0:
            transactions.append({
                "name": statement.get("name", "Unknown"),
                "date": statement.get("date"),
                "amount": statement.get("amount", 0),
                "category": category,
                "type": "deposit"
            })
        else:
            if statement.get("amount") > hi:
                hi = statement.get("amount")
                high = f'''
                    "rank": "highest",
                    "name": {statement.get("name", "Unknown")},
                    "date": {statement.get("date")},
                    "amount": {statement.get("amount", 0)},
                    "category": {category}
                '''

            if statement.get("amount") < low:
                low = statement.get("amount")
                lowest = f'''
                    "rank": "lowest",
                    "name": {statement.get("name", "Unknown")},
                    "date": {statement.get("date")},
                    "amount": {statement.get("amount")},
                    "category": {category}
                '''



            transactions.append({
                "name": statement.get("name", "Unknown"),
                "date": statement.get("date"),
                "amount": statement.get("amount", 0),
                "category": category,
                "type": "withdrawal"
            })



        category_totals[category] += round(-1 * statement.get("amount", 0), 2)


    transactions.reverse()
    transactions.append({high})
    transactions.append({lowest})
    return transactions, category_totals


def financial_advisor(statements):
  system = {"role": "system", "content": instructions}

  user = []
  for statement in statements:
    user.append({"role": "user", "content": statement})


  completion = client.chat.completions.create(
    model="gpt-4-turbo",
    messages=[system]+user,

  )

  return completion.choices[0].message.content, system, user

def getStatements(file):
    url = "https://api.veryfi.com/api/v8/partner/bank-statements"
    encoded_file = base64.b64encode(file.read()).decode("utf-8")
    payload = json.dumps({
      "file_data": encoded_file
    })
    headers = {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
      'CLIENT-ID': os.environ.get('OTHER_CLIENT'),
      'AUTHORIZATION': os.environ.get('OTHER_KEY')
    }

    response = requests.request("POST", url, headers=headers, data=payload)

    response = response.json()

    transactions = response.get("transactions")


    statements = []

    for order in transactions:
        if order.get("credit_amount"):
            statements.append(f'{{"description": "{order.get("description")}", "amount": "{order.get("credit_amount")}", "date": "{order.get("date")}"}}')
        else:
            statements.append(f'{{"description": "{order.get("description")}", "amount": "-{order.get("debit_amount")}", "date": "{order.get("date")}"}}')

    return statements

@app.before_request
def clear_session_on_refresh():
    session.permanent = False
    if request.path == "/":
        session.clear()

@app.route('/')
def home():
    global categories
    global current
    categories = None
    current = "empty"
    if "conversation" not in session:
        session["conversation"] = []
    session.permanent = True
    greeting = client.chat.completions.create(
        model="gpt-4-turbo",
        messages=[
            {"role": "system", "content": "youre a financial advisor greeting the user. tell the user to either upload bank statements or connect to their bank using the buttons below to begin. DO NOT MAKE A FORM OR A BUTTON. ONLY TEXT. respond in html <body>format with <h1>"},
            {"role": "user", "content": "hello"}
        ],

    )

    begin = greeting.choices[0].message.content



    return render_template('index.html',ai = begin)


@app.route('/advice', methods=['POST'])
def advice():
    global banksss
    global categories
    global current
    bank_statement = ""

    session.permanent = True
    if "conversation" not in session:
        session["conversation"] = []



    if categories:

        text_input = request.form.get("text")



        if current == categories:
            if text_input:
                session["conversation"].append({"role": "user", "content": str(banksss)})
                session["conversation"].append({"role": "system", "content": "respond to everything kindly as a financial advisor. and look at past chats to answer questions.  ANSWER IN HTML FORMAT AND MAKE SURE ITS STRUCTURED WELL SO THE USER CAN READ WELL INSTEAD OF A BIG PARAGRAPH! NEVER DISCOURAGE SENDING BANK STATEMENTS. ENCOURAGE SENDING BANK STATEMENTS FOR BEST ANALYSIS. ALWAYS REFER TO THE BANK STATEMENTS IF THERE ARE ANY SENT. ALWAYS ASK IF THE USER HAS ANY QUESTIONS LEFT"})
                session["conversation"].append({"role": "user", "content": text_input})


        if current != categories:

            session["conversation"].append({"role": "system","content": bankInstructions})
            current = categories



        try:
            completion = client.chat.completions.create(
                model="gpt-4-turbo",
                messages = session["conversation"]
            )
            ai_response = completion.choices[0].message.content.replace("```", "")
            ai_response = ai_response.replace("html", "")
            session["conversation"].append({"role": "assistant", "content": ai_response})

            session.modified = True

        except Exception as e:
            ai_response = f"Error connecting to AI service: {str(e)}"


        return jsonify({"reply": ai_response})

    else:
        if categories:
            categories = None

        if "pdf" in request.files and request.files["pdf"].filename:
            file = request.files["pdf"]
            bank_statement = getStatements(file)


        text_input = request.form.get("text")


        chat = ""
        if bank_statement:
            chat,system,user = financial_advisor(bank_statement)
            session["conversation"].append({"role": "assistant", "content": chat})




        if text_input:
            session["conversation"].append({"role": "system", "content": "respond to everything kindly as a financial advisor. and look at past chats to answer questions.  ANSWER IN HTML FORMAT! NEVER DISCOURAGE SENDING BANK STATEMENTS. ENCOURAGE SENDING BANK STATEMENTS FOR BEST ANALYSIS. ALWAYS REFER TO THE BANK STATEMENTS IF THERE ARE ANY SENT AND ALWAYS LOOK AT THE DATES AND ORDER THE TRANSACTIONS USING THE DATE. THE ORDER THIS LIST IS IN SHOULD GO BY DATE NOT THE ACTUAL ORDER. ALWAYS ASK IF THE USER HAS ANY QUESTIONS LEFT"})
            session["conversation"].append({"role": "user", "content": text_input})


        try:
            if len(chat)>3:
                ai_response = chat.replace("```","")
                ai_response = ai_response.replace("html", "")
            else:
                completion = client.chat.completions.create(
                    model="gpt-4-turbo",
                    messages=[{"role": "user", "content": str(banksss)}] + session["conversation"]
                )
                ai_response = completion.choices[0].message.content.replace("```","")
                ai_response = ai_response.replace("html","")
                session["conversation"].append({"role": "assistant", "content": ai_response})

            session.modified = True

        except Exception as e:
            ai_response = f"Error connecting to AI service: {str(e)}"


        return jsonify({"reply": ai_response})

@app.route('/save', methods=['POST'])
def save():
    global t
    global banksss
    global categories
    global current

    if "pdf" in request.files and request.files["pdf"].filename:
        session.clear()

        categories = None
        current = "empty"

        file = request.files["pdf"]
        reader = PdfReader(file)
        ting = "\n".join([page.extract_text() or "" for page in reader.pages])
        banksss=ting

    return jsonify({"value": banksss})

@app.route("/get_link_token", methods=["GET"])
def create():
    url = f"{PLAID_BASE_URL}/link/token/create"
    payload = {
        "client_id": clientId,
        "secret": key,
        "client_name": "Your App",
        "user": {"client_user_id": "userfr"},
        "products": ["transactions"],
        "country_codes": ["US"],
        "language": "en"
    }
    response = requests.post(url, json=payload)


    return jsonify(response.json())


@app.route("/exchange_public_token", methods=["POST"])
def token():
    global t
    global categories
    global banksss
    data = request.json
    public_token = data.get("public_token")

    if not public_token:
        return jsonify({"error": "Missing public_token"}), 400

    url = f"{PLAID_BASE_URL}/item/public_token/exchange"
    payload = {
        "client_id": clientId,
        "secret": key,
        "public_token": public_token
    }
    response = requests.post(url, json=payload)
    trans = response.json()
  
    time.sleep(5)
    if "access_token" in trans:
        session.clear()
        t = trans["access_token"]
        transactions, categorize = get_transactions(t)
        categories = categorize
        banksss = transactions
        if "conversation" not in session:
            session["conversation"] = []
        session["conversation"].append({"role": "user", "content": str(categories)})
    return jsonify(trans)

@app.route("/analysis", methods=["POST"])
def analysis():
    global t
    transactions, categorize= get_transactions(t)




    return jsonify(categorize)


if __name__ == "__main__":
    app.run(debug=True)
