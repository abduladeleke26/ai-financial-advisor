import time
from openai import OpenAI
from pypdf import PdfReader
from flask import Flask, render_template, request, session, jsonify, flash, redirect, url_for
import base64
import json
import requests
import datetime
from collections import defaultdict
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from sqlalchemy.orm.attributes import flag_modified
import os

app = Flask(__name__, static_folder="static", template_folder="templates")
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DB_URI", "sqlite:///database.db")
app.secret_key = "your-secret-key"
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(80), nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    categories = db.Column(db.Text, nullable=True)
    info = db.Column(db.Text, nullable=True)
    files = db.Column(db.Boolean, nullable=True)


with app.app_context():
    db.create_all()

clientId = os.environ.get('PLAID_CLIENT')
key = os.environ.get('PLAID_KEY')
PLAID_BASE_URL = f"https://production.plaid.com"

t = ""

client = OpenAI(api_key=os.environ.get('AI_KEY'))

banksss = ""
categories = None
logged_in = False
name = None
user = None
files = False
error = None
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
  
  THERE SHOULD NEVER BE TWO ROWS WITH THE SAME NAME. SUM EVERYTHING UP.

  no table should have two of the same categories.

  every table should have a total (total withdrawals, total deposits)

  every table should have a title (withdrawals, deposits) in <h2></h2>

  make sure both tables are always separate they cannot touch.

  keep deposits and withdrawals separate.

  Finally give financial advice. Talk about where the user did good and what needs to be improved.

  THE ONLY THING I SHOULD SEE IS THE TITLE, TABLES, AND THE FINANCIAL ADVICE.


  """


def get_transactions(token):
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

    response = requests.post(url, json=payload)
    response = response.json()
    response = response["transactions"]

    transactions = []

    category_totals = defaultdict(float)
    for statement in response:

        category = statement.get("personal_finance_category")
        category = category.get("primary")
        category = category.replace("_", " ")
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
            transactions.append({
                "name": statement.get("name", "Unknown"),
                "date": statement.get("date"),
                "amount": statement.get("amount", 0),
                "category": category,
                "type": "withdrawal"
            })

        category_totals[category] += round(-1 * statement.get("amount", 0), 2)

    transactions.reverse()

    return transactions, category_totals


def financial_advisor(statements):
    system = {"role": "system", "content": instructions}

    user = []
    for statement in statements:
        user.append({"role": "user", "content": statement})

    completion = client.chat.completions.create(
        model="gpt-4-turbo",
        messages=[system] + user,

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
    global banksss
    global current
    global logged_in
    global error
    global user
    categories = None
    current = "empty"
    if "conversation" not in session:
        session["conversation"] = []
    session.permanent = True
    if logged_in and isinstance(user, User):
        greeting = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "system",
                 "content": "youre a financial advisor greeting the user. tell the user to either upload bank statements or connect to their bank using the buttons below to begin. DO NOT MAKE A FORM OR A BUTTON. ONLY TEXT. respond in html <body>format with <h1>"},
                {"role": "system",
                 "content": f"the user name is {name}. welcome the user back. tell the user to either continue asking questions or to either upload bank statements or connect to their bank for advice on a different account"},
                {"role": "user", "content": "hello"}
            ],
        )

        categories = user.categories
        banksss = user.info
        current = categories
        files = user.files
        if not files:
            print("bank")
            menn = client.chat.completions.create(
                model="gpt-4-turbo",
                messages=[
                    {"role": "system", "content": bankInstructions},
                    {"role": "user", "content": str(categories)},
                ]
            )
        else:
            print("files")
            menn = client.chat.completions.create(
                model="gpt-4-turbo",
                messages=[
                    {"role": "system", "content": instructions},
                    {"role": "user", "content": str(categories)},
                ]
            )

    else:
        greeting = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "system",
                 "content": "youre a financial advisor greeting the user. tell the user to either upload bank statements or connect to their bank using the buttons below to begin. DO NOT MAKE A FORM OR A BUTTON. ONLY TEXT. respond in html <body>format with <h1>"},
                {"role": "user", "content": "hello"}
            ],
        )

        categories = None
        banksss = None

    begin = greeting.choices[0].message.content
    if categories:
        info = menn.choices[0].message.content

    return render_template('index.html', ai=begin, logged_in=logged_in, info=info if categories else None, error=error)


@app.route('/login', methods=['POST'])
def login():
    global name
    global logged_in
    global error
    global user
    username = request.form['username']
    password = request.form['password']
    user = User.query.filter_by(username=username).first()
    if user and bcrypt.check_password_hash(user.password, password):
        name = user.full_name
        logged_in = True
        error = None
        session["user_id"] = user.id
        return redirect(url_for('home'))
    else:
        error = "Username or Password is Wrong"
        return redirect(url_for('home'))


@app.route('/signupfr', methods=['POST'])
def signupfr():
    full_name = request.form['name']
    username = request.form['username']
    password = request.form['password']
    confirm = request.form['confirm password']

    if password == confirm:

        existing_user = User.query.filter_by(username=username).first()

        if existing_user:
            message = "This user is taken."
            return render_template('sign up.html', message=message)

        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        new_user = User(full_name=full_name, username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('home'))
    else:
        message = "password and confirm password is not the same"
        return render_template('sign up.html',message=message)


@app.route('/logout')
def logout():
    global logged_in
    logged_in = False
    return redirect(url_for('home'))


@app.route('/advice', methods=['POST'])
def advice():
    global banksss
    global categories
    global current
    global files
    bank_statement = ""

    session.permanent = True
    if "conversation" not in session:
        session["conversation"] = []



    if files == False:

        text_input = request.form.get("text")
        print("this is a bank")


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

        print("this is a file")
        if "pdf" in request.files and request.files["pdf"].filename:
            file = request.files["pdf"]
            bank_statement = getStatements(file)

        text_input = request.form.get("text")

        chat = ""
        if bank_statement:
            chat, system, userr = financial_advisor(bank_statement)
            session["conversation"].append({"role": "assistant", "content": chat})

        if text_input:
            session["conversation"].append({"role": "system", "content": "respond to everything kindly as a financial advisor. and look at past chats to answer questions.  ANSWER IN HTML FORMAT! NEVER DISCOURAGE SENDING BANK STATEMENTS. ENCOURAGE SENDING BANK STATEMENTS FOR BEST ANALYSIS. ALWAYS REFER TO THE BANK STATEMENTS IF THERE ARE ANY SENT AND ALWAYS LOOK AT THE DATES AND ORDER THE TRANSACTIONS USING THE DATE. THE ORDER THIS LIST IS IN SHOULD GO BY DATE NOT THE ACTUAL ORDER. ALWAYS ASK IF THE USER HAS ANY QUESTIONS LEFT"})
            session["conversation"].append({"role": "user", "content": text_input})

        try:
            if len(chat) > 3:
                ai_response = chat.replace("```", "")
                ai_response = ai_response.replace("html", "")
            else:
                completion = client.chat.completions.create(
                    model="gpt-4-turbo",
                    messages=[{"role": "user", "content": str(banksss)}] + session["conversation"]
                )
                ai_response = completion.choices[0].message.content.replace("```", "")
                ai_response = ai_response.replace("html", "")
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
    global user

    if "pdf" in request.files and request.files["pdf"].filename:
        session.clear()

        print(user)

        categories = None
        current = "empty"

        file = request.files["pdf"]
        reader = PdfReader(file)
        bankStatements = getStatements(file)
        ting = "\n".join([page.extract_text() or "" for page in reader.pages])

        if isinstance(user, User):
            user = User.query.filter_by(id=user.id).first()

            user.categories = json.dumps(bankStatements)
            user.info = None
            user.files = True

            flag_modified(user, "categories")
            flag_modified(user, "info")
            flag_modified(user, "files")
            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                print("Database commit failed:", str(e))

        banksss = ting

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
    global files
    global user

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

    if "access_token" in trans:
        session.clear()
        t = trans["access_token"]
        time.sleep(15)
        print(user)
        print("yesssss")
        files = False
        transactions, categorize = get_transactions(t)
        if isinstance(user, User):
            user = User.query.filter_by(id=user.id).first()

            user.categories = json.dumps(categorize)
            user.info = json.dumps(transactions)
            user.files = False

            flag_modified(user, "categories")
            flag_modified(user, "info")
            flag_modified(user, "files")

            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                print("Database commit failed:", str(e))

        categories = categorize
        banksss = transactions

        if "conversation" not in session:
            session["conversation"] = []
        session["conversation"].append({"role": "user", "content": str(categorize)})

    return jsonify(trans)


@app.route("/analysis", methods=["POST"])
def analysis():
    global t
    transactions, categorize = get_transactions(t)
    return jsonify(categorize)


@app.route('/signup')
def signup():
    return render_template('sign up.html')


if __name__ == "__main__":
    app.run(debug=True)