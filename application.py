import os
import requests

from flask import Flask, session, render_template, url_for, request, redirect
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

app = Flask(__name__)

# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))


@app.route("/")
def index():
	if "username" in session:
		return redirect("search")
	else:
		return render_template("index.html")

@app.route("/signup")
def signup():
	return render_template("signup.html")

@app.route("/signup", methods=["POST"])
def register():
	name = request.form.get("name")
	password = request.form.get("password")
	if not name or not password:
		return render_template("signup.html", message="Please enter a unique name and a password.")
	try:
		db.execute("INSERT INTO users (name, password) VALUES (:name, :password)", {"name": name, "password": password})
	except:
		return render_template("signup.html", message="This name is already taken.")
	db.commit()
	return render_template("index.html", message="You are now registered!")


@app.route('/login', methods=['GET', 'POST'])
def login():
	if request.method == 'GET':
		return render_template("login.html")
	if request.method == 'POST':
		session["username"] = request.form["name"]
		name = request.form.get("name")
		password = request.form.get("password")
		if not name or not password:
			return render_template("login.html", message="Please enter your name and password.")
		if db.execute("SELECT * FROM users WHERE name = :name AND password = :password", {"name": name, "password": password}).fetchone():
			db.commit()
			return redirect("search")
		else:
			db.commit()
			return render_template("login.html", message="Please enter a valid name and password.")

@app.route('/logout')
def logout():
	session.pop('username', None)
	return render_template("index.html")

@app.route('/search', methods=['GET', 'POST'])
def search():
	if request.method == 'GET':
		return render_template("search.html")
	if request.method == 'POST':
		try:
			if request.form.get("search-term") == "":
				return render_template("error.html", message="Please enter a search term.")
			searchterm = "%" + request.form.get("search-term") + "%"
			books = db.execute("SELECT * FROM books WHERE title ILIKE :searchterm OR author ILIKE :searchterm OR isbn ILIKE :searchterm", {"searchterm": searchterm}).fetchall()
			if books == []:
				return render_template("error.html", message="Oops! We couldn't find that book.")
			db.commit()
			return render_template("results.html", books=books, searchterm=searchterm.replace('%', ''))
		except:
			return render_template("error.html", message="Oops! We couldn't find that book.")


@app.route('/books')
def books():
	return render_template("book.html")

@app.route('/books/<int:book_id>', methods=['GET', 'POST'])
def book(book_id):
	#Fetches book info
	book = db.execute("SELECT * FROM books WHERE id = :id", {"id": book_id}).fetchone()
	if book is None:
		return render_template("error.html", message="No such book.")

	res = requests.get("https://www.goodreads.com/book/review_counts.json", params={"key": "UUmlMSE99UxIV7uBXUxD5g", "isbns": book.isbn})
	if res.status_code != 200:
		raise Exception("Error: API request unsuccessful.")
	data = res.json()
	average = data['books'][0]['average_rating']

	#DisplayReviews
	reviews = db.execute("SELECT * FROM reviews WHERE book_isbn = :book_id", {"book_id": book_id}).fetchall()
	if reviews == []:
		reviews = "No reviews yet."

	#PostReviews
	if request.method == 'POST':
		if db.execute("SELECT * FROM reviews WHERE username = :user AND book_isbn = :book_id", {"user": session["username"], "book_id": book_id}).fetchall():
			return render_template("error.html", message="You have already submitted a review for this book.")
		elif not request.form.get("content") or not request.form.get("rating"):
			return render_template("error.html", message="Please provide a rating and some text in your review.")
		else:
			content = request.form.get("content")
			rating = request.form.get("rating")
			db.execute("INSERT INTO reviews (username, content, rating, book_isbn) VALUES (:user, :content, :rating, :book_id)", {"user": session["username"], "content": content, "rating": rating, "book_id": book_id})
			db.commit()
	return render_template("book.html", book=book, average=average, reviews=reviews)



