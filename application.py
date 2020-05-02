import os
from flask import Flask, session, render_template, request, redirect, url_for, jsonify
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
import hashlib
import math
import requests

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
    session["signinStatus"]=0
    red=session.get("redirect")!=None
    if red:
        session.pop("redirect")
    if session.get("user_id")!=None:
        return redirect(url_for('mainpage'))
    else:
        return render_template("index.html", redirect=red)

@app.route("/login")
def login():
    if session.get("user_id")!=None:
        return redirect(url_for('mainpage'))
    return render_template("login.html", message=session["signinStatus"])

@app.route("/log1n", methods=["POST"])
def credcheck():
    username=request.form.get("username")
    if username=="":
        session["signinStatus"]=-2 #no username entered
        return redirect(url_for('login', message=session["signinStatus"]))
    if len(db.execute("SELECT username FROM users WHERE username=:val", {"val" : username}).fetchall())!=0:
        storedAcc=db.execute("SELECT * FROM users WHERE username=:val", {"val" : username}).fetchall()[0]
        print(storedAcc)
        salt=storedAcc.salt.encode("latin-1")
        key=storedAcc.key.encode("latin-1")
        print(key, salt, hashlib.pbkdf2_hmac('sha256', request.form.get("pass").encode('utf-8'), salt, 100000, dklen=32))
        if key==hashlib.pbkdf2_hmac('sha256', request.form.get("pass").encode('utf-8'), salt, 100000, dklen=32):
            session["user_id"]=storedAcc.id
            return redirect(url_for('mainpage'))
        else:
            session["signinStatus"]=5  #Incorrect password
            return redirect(url_for('login'))
    else:
        session["signinStatus"]=4  #Account doesn't exist
        return redirect(url_for('login'))

@app.route("/register")
def register():
    if session.get("user_id")!=None:
        return redirect(url_for('mainpage'))
    return render_template("register.html", message=session["signinStatus"])

@app.route("/reg1ster", methods=["POST"])
def newaccount():
    salt = os.urandom(32)
    username=request.form.get("username")
    if username=="":
        session["signinStatus"]=-1 #no username entered
        return redirect(url_for('register'))
    elif len(db.execute("SELECT username FROM users WHERE username=:val", {"val" : username}).fetchall())!=0:
        session["signinStatus"]=1  #user already exists
        return redirect(url_for('register'))
    elif len(request.form.get("pass"))<8:
        session["signinStatus"]=2  #password too short
        return redirect(url_for('register'))
    else:
        key=hashlib.pbkdf2_hmac('sha256', request.form.get("pass").encode('utf-8'), salt, 100000, dklen=32)
        db.execute("INSERT INTO users(username, key, salt) VALUES(:val1, :val2, :val3)", {"val1" : username, "val2" : key.decode("latin-1"), "val3" : salt.decode("latin-1")})
        db.commit()
        session["signinStatus"]=3  #new account created
        return redirect(url_for('login'))

@app.route("/signout/")
def signout():
    session.pop('user_id')
    return redirect(url_for('index'))

@app.route("/main/")
def mainpage():
    if session.get("user_id")==None:
        session["redirect"]=1
        return redirect(url_for('index'))
    else:
        return render_template("main.html", name=" "+db.execute("SELECT username FROM users WHERE id=:val", {"val" : session["user_id"]}).fetchall()[0].username, search=0)

@app.route("/main/search", methods=["POST"])
def search():
    print(request.form)
    if request.form.get("search")=="":
        return redirect(url_for('main'))
    if request.form.get('search')!=None:
        session["terms"]=request.form.get("search").upper()
        session["pageNum"]=1
    if request.form.get('form2')!=None:
        session["pageNum"]+=1
    if request.form.get('form3')!=None:
        session["pageNum"]-=1
    books=db.execute("SELECT * FROM books WHERE upper(ISBN) LIKE :terms OR upper(title) LIKE :terms OR upper(author) LIKE :terms LIMIT 10 OFFSET :page", {"terms" : "%"+session["terms"]+"%" , "page" : (session["pageNum"]-1)*10})
    print("Look here!!!", db.execute("SELECT COUNT(*) FROM books WHERE upper(ISBN) LIKE :terms OR upper(title) LIKE :terms OR upper(author) LIKE :terms", {"terms" : "%"+session["terms"]+"%"}).fetchall()[0][0])
    pagecount=math.ceil(int(db.execute("SELECT COUNT(*) FROM books WHERE upper(ISBN) LIKE :terms OR upper(title) LIKE :terms OR upper(author) LIKE :terms", {"terms" : "%"+session["terms"]+"%"}).fetchall()[0][0])/10.0)
    return render_template("main.html", name=" "+db.execute("SELECT username FROM users WHERE id=:val", {"val" : session["user_id"]}).fetchall()[0].username, search=1, books=books, terms=session["terms"], page=session["pageNum"], pagecount=pagecount)

@app.route("/main/<ISBN>")
def bookpage(ISBN):
    if session.get("user_id")==None:
        session["redirect"]=ISBN
        return redirect(url_for('index'))
    else:
        session["isbn"]=ISBN
        res = requests.get("https://www.goodreads.com/book/review_counts.json", params={"key": "qZvtqAr3jIWI7t8E7gpnyw", "isbns": ISBN})
        gr_data=res.json()
        print(gr_data["books"])
        betterreads_rating=db.execute("SELECT avg(rating) FROM reviews WHERE ISBN=:ISBN", {"ISBN" : ISBN}).fetchall()[0][0]
        goodreads_rating=gr_data["books"][0]["average_rating"]
        goodreads_samplesize=gr_data["books"][0]["work_ratings_count"]
        book=db.execute("SELECT * FROM books WHERE isbn=:ISBN", {"ISBN" : ISBN}).fetchall()[0]
        reviews=db.execute("SELECT isbn, rating, review, user_id, username FROM reviews r JOIN users u ON r.user_id=u.id WHERE ISBN=:ISBN", {"ISBN" : ISBN}).fetchall()
        betterreads_samplesize=len(reviews)
        newPost=len(db.execute("SELECT user_id FROM reviews WHERE user_id=:id AND isbn=:ISBN", {'id':session["user_id"], 'ISBN' : ISBN}).fetchall())==0
        return render_template("book.html", ISBN=ISBN, betterreads_rating=betterreads_rating, betterreads_samplesize=betterreads_samplesize, goodreads_rating=goodreads_rating, goodreads_samplesize=goodreads_samplesize, book=book, reviews=reviews, session_user=db.execute("SELECT username FROM users WHERE id=:id", {'id':session["user_id"]}).fetchall()[0].username, newPost=newPost)

@app.route("/reviewrequest", methods=["POST"])
def submitReview():
    isbn=session["isbn"]
    if request.form.get('rating')!=None:
        rating=int(request.form.get("rating"))
        review=request.form.get("review")
        db.execute("DELETE FROM reviews WHERE user_id=:id and isbn=:isbn", {'id':session["user_id"], "isbn" : session["isbn"]})
        if review=="":
            db.execute("INSERT INTO reviews(isbn, rating, user_id) VALUES (:isbn, :rating, :user)", {'isbn' : isbn, 'rating' : rating, 'user' : session['user_id']})
        else:
            db.execute("INSERT INTO reviews(isbn, rating, review, user_id) VALUES (:isbn, :rating, :review, :user)", {'isbn' : isbn, 'rating' : rating, 'review' : review, 'user' : session['user_id']})
        db.commit()
    if request.form.get('del')!=None:
        db.execute("DELETE FROM reviews WHERE user_id=:id and isbn=:isbn", {'id':session["user_id"], "isbn" : session["isbn"]})
        db.commit()
    return redirect(url_for('bookpage', ISBN=isbn))

@app.route("/api/<ISBN>")
def get_api(ISBN):
    if len(db.execute("SELECT * FROM books WHERE isbn=:ISBN", {"ISBN" : ISBN}).fetchall())==0:
        return "Error<br>Status code: <b>404</b>"
    else:
        book=db.execute("SELECT * FROM books WHERE isbn=:ISBN", {"ISBN" : ISBN}).fetchall()[0]
        review_count=len(db.execute("SELECT * FROM reviews WHERE ISBN=:ISBN", {"ISBN" : ISBN}).fetchall())
        average_score=None
        if review_count!=0:
            average_score=float(db.execute("SELECT avg(rating) FROM reviews WHERE ISBN=:ISBN", {"ISBN" : ISBN}).fetchall()[0][0])
        return jsonify(title=book.title, author=book.author, year=book.year, isbn=ISBN, review_count=review_count, average_score=average_score)
